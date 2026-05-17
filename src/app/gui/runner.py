from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from PySide6 import QtCore

from ..core.database.db import Database
from ..core.sync.executor import ActionExecutor
from ..core.sync.service import SyncService
from ..core.events.event_bus import EventBus


@dataclass(frozen=True)
class SyncRequest:
    playlist_cfg: Dict[str, Any]
    apply: bool = True
    db_path: Path = Path("db/app.db")
    cancel_flag: threading.Event | None = None
    pause_flag: threading.Event | None = None


class SyncRunner(QtCore.QObject):
    """
    Runs a sync in the background to keep the UI responsive.
    """

    finished = QtCore.Signal(bool, str)

    def __init__(self, bus: EventBus, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._bus = bus
        self._req: SyncRequest | None = None

    @QtCore.Slot(object)
    def set_request(self, req: SyncRequest) -> None:
        self._req = req

    @QtCore.Slot()
    def run_current(self) -> None:
        if self._req is None:
            self.finished.emit(False, "no request")
            return
        self.run(self._req)

    @QtCore.Slot(object)
    def run(self, req: SyncRequest) -> None:
        try:
            if req.cancel_flag is not None and req.cancel_flag.is_set():
                self.finished.emit(False, "cancelled")
                return

            db = Database(req.db_path.resolve())
            service = SyncService(db)
            executor = ActionExecutor(db, concurrency=int(req.playlist_cfg.get("max_parallel_downloads", 2) or 2), event_bus=self._bus)

            actions = service.sync_from_config(req.playlist_cfg)
            if req.cancel_flag is not None and req.cancel_flag.is_set():
                self.finished.emit(False, "cancelled")
                return
            if req.apply and actions:
                cancel_check = req.cancel_flag.is_set if req.cancel_flag is not None else None
                pause_check = req.pause_flag.is_set if req.pause_flag is not None else None
                asyncio.run(executor.execute(actions, req.playlist_cfg, cancel_check=cancel_check, pause_check=pause_check))

            if req.cancel_flag is not None and req.cancel_flag.is_set():
                self.finished.emit(False, "cancelled")
            else:
                self.finished.emit(True, "done")
        except Exception as exc:
            self.finished.emit(False, str(exc))

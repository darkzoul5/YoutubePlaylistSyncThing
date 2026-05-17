from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ...config.settings import Settings
from ...core.database.db import Database
from ...core.utils.yt import extract_playlist_id
from ..smooth_scroll import enable_smooth_scrolling
from ..config_store import load_config, normalize_config, save_config


@dataclass(frozen=True)
class PlaylistRow:
    name: str
    url: str
    download_mode: str
    max_download_quality: str
    save_path: str


class PlaylistManagerPage(QtWidgets.QWidget):
    cancel_requested = QtCore.Signal()
    sync_one_requested = QtCore.Signal(int)
    sync_all_requested = QtCore.Signal()
    pause_requested = QtCore.Signal()
    resume_requested = QtCore.Signal()

    def __init__(
        self,
        settings: Settings,
        *,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._config_path = getattr(settings, "path", None)
        self._config: dict[str, Any] = {}
        self._download_state_by_pid: dict[str, dict[str, Any]] = {}
        self._suppress_autosave = False
        self._autosave_timer = QtCore.QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(600)
        self._autosave_timer.timeout.connect(self._autosave_now)

        header = QtWidgets.QLabel("Playlists")
        header.setObjectName("pageTitle")

        self._list = QtWidgets.QListWidget()
        # Selection-based UI is intentionally disabled; actions happen per-card.
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self._list.setSpacing(8)
        self._list.setUniformItemSizes(False)
        self._list.setWordWrap(True)
        self._list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        enable_smooth_scrolling(self._list)

        self._add_btn = QtWidgets.QPushButton("Add")
        self._add_btn.clicked.connect(self._add_playlist)
        self._save_btn = QtWidgets.QPushButton("Save config")
        self._save_btn.clicked.connect(self._save_config)

        self._sync_all_btn = QtWidgets.QPushButton("Sync all")
        self._sync_all_btn.clicked.connect(self.sync_all_requested.emit)

        self._cancel_btn = QtWidgets.QPushButton("Cancel all")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_sync)

        self._refresh_btn = QtWidgets.QPushButton("Reload config")
        self._refresh_btn.clicked.connect(self.reload_from_config)

        self._status = QtWidgets.QLabel("")
        self._status.setWordWrap(True)
        self._sync_state = QtWidgets.QLabel("")
        self._sync_state.setWordWrap(True)
        self._sync_state.setStyleSheet("color: #9fb0c6;")

        top = QtWidgets.QHBoxLayout()
        top.addWidget(header)
        top.addStretch(1)
        top.addWidget(self._add_btn)
        top.addWidget(self._save_btn)
        top.addWidget(self._sync_all_btn)
        top.addWidget(self._cancel_btn)
        top.addWidget(self._refresh_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._sync_state)
        layout.addWidget(self._status)

        self.reload_from_config()

    def _rows_from_settings(self) -> list[PlaylistRow]:
        rows: list[PlaylistRow] = []
        for idx, pl in enumerate(self._settings.playlists, start=1):
            name = str(pl.get("name") or f"Playlist {idx}")
            rows.append(
                PlaylistRow(
                    name=name,
                    url=str(pl.get("url") or ""),
                    download_mode=str(pl.get("download_mode") or ""),
                    max_download_quality=str(pl.get("max_download_quality") or ""),
                    save_path=str(pl.get("save_path") or ""),
                )
            )
        return rows

    @QtCore.Slot()
    def reload_from_config(self) -> None:
        try:
            self._suppress_autosave = True
            self._settings = Settings()
            self._config_path = getattr(self._settings, "path", None)
            if self._config_path is None:
                raise RuntimeError("Config path not available")
            self._config = normalize_config(load_config(self._config_path).data)
            rows = self._rows_from_settings()
        except Exception as exc:
            self._status.setText(f"Failed to load config: {exc}")
            return
        finally:
            self._suppress_autosave = False

        # Optional DB metadata (last_sync). If DB is missing/corrupt, keep UI usable.
        last_sync_by_id: dict[str, str] = {}
        try:
            db = Database(Path("db/app.db").resolve())
            for r in rows:
                pid = extract_playlist_id(r.url) or r.url
                ls = db.get_playlist_last_sync(pid)
                if ls:
                    last_sync_by_id[pid] = str(ls)
        except Exception:
            last_sync_by_id = {}

        self._list.clear()
        for idx, r in enumerate(rows):
            pid = extract_playlist_id(r.url) or r.url
            widget = _PlaylistCard(r, index=idx, last_sync=last_sync_by_id.get(pid))
            widget.sync_clicked.connect(self.sync_one_requested.emit)
            widget.remove_clicked.connect(self._remove_at_index)
            widget.cancel_clicked.connect(lambda _pid: self._cancel_sync())
            widget.pause_changed.connect(self._on_pause_changed)
            widget.changed.connect(self._schedule_autosave)
            item = QtWidgets.QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

        cfg_path = getattr(self._settings, "path", None)
        self._status.setText(f"Loaded {len(rows)} playlists from {cfg_path}.")

    @QtCore.Slot()
    def _cancel_sync(self) -> None:
        # Actual cancellation is handled by MainWindow; this is UI intent.
        self._status.setText("Cancelling…")
        self.cancel_requested.emit()

    def set_running(self, running: bool) -> None:
        self._sync_all_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        self._save_btn.setEnabled(not running)
        self._add_btn.setEnabled(not running)
        self._refresh_btn.setEnabled(not running)
        # Keep the list enabled so per-card Pause/Cancel remains clickable.
        self._list.setEnabled(True)
        # But freeze editing while a sync is running to avoid racey config edits.
        for i in range(self._list.count()):
            item = self._list.item(i)
            w = self._list.itemWidget(item)
            if isinstance(w, _PlaylistCard):
                w.set_editing_enabled(not running)

    @QtCore.Slot()
    def _add_playlist(self) -> None:
        r = PlaylistRow(
            name="New Playlist",
            url="https://www.youtube.com/playlist?list=",
            download_mode="video",
            max_download_quality="1080p",
            save_path="./downloads",
        )
        widget = _PlaylistCard(r, index=self._list.count())
        widget.sync_clicked.connect(self.sync_one_requested.emit)
        widget.remove_clicked.connect(self._remove_at_index)
        widget.cancel_clicked.connect(lambda _pid: self._cancel_sync())
        widget.pause_changed.connect(self._on_pause_changed)
        widget.changed.connect(self._schedule_autosave)
        item = QtWidgets.QListWidgetItem()
        item.setSizeHint(widget.sizeHint())
        self._list.addItem(item)
        self._list.setItemWidget(item, widget)
        self._schedule_autosave()

    @QtCore.Slot()
    def _remove_at_index(self, index: int) -> None:
        if index < 0 or index >= self._list.count():
            return
        self._list.takeItem(index)
        self._reindex_cards()
        self._schedule_autosave()

    @QtCore.Slot(bool)
    def _on_pause_changed(self, paused: bool) -> None:
        if paused:
            self.pause_requested.emit()
            self._sync_state.setText("Paused")
        else:
            self.resume_requested.emit()
            self._sync_state.setText("Resumed")

    def _table_to_playlists(self) -> list[dict[str, Any]]:
        playlists: list[dict[str, Any]] = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            w = self._list.itemWidget(item)
            if not isinstance(w, _PlaylistCard):
                continue
            pl = w.to_dict()
            playlists.append(pl)
        return playlists

    @QtCore.Slot()
    def _save_config(self) -> None:
        if self._config_path is None:
            self._status.setText("No config path loaded.")
            return
        try:
            if not self._validate_all(show_status=True):
                return
            data = dict(self._config or {})
            data["playlists"] = self._table_to_playlists()
            save_config(self._config_path, data)
            self._status.setText(f"Saved {len(data['playlists'])} playlists to {self._config_path}.")
            # Reload settings to reflect merged defaults
            self.reload_from_config()
        except Exception as exc:
            self._status.setText(f"Failed to save config: {exc}")

    def _reindex_cards(self) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            w = self._list.itemWidget(item)
            if isinstance(w, _PlaylistCard):
                w.set_index(i)

    def _validate_all(self, *, show_status: bool) -> bool:
        ok = True
        for i in range(self._list.count()):
            item = self._list.item(i)
            w = self._list.itemWidget(item)
            if isinstance(w, _PlaylistCard):
                errs = w.validate()
                w.set_status("; ".join(errs) if errs else "")
                if errs:
                    ok = False
        if not ok and show_status:
            self._status.setText("Fix invalid playlists before saving/syncing.")
        return ok

    @QtCore.Slot()
    def _schedule_autosave(self) -> None:
        if self._suppress_autosave:
            return
        if not self.isEnabled():
            return
        self._autosave_timer.start()

    @QtCore.Slot()
    def _autosave_now(self) -> None:
        if self._config_path is None:
            return
        if self._suppress_autosave:
            return
        if not self._validate_all(show_status=False):
            # Don't autosave invalid configs; user sees inline errors.
            return
        try:
            data = dict(self._config or {})
            data["playlists"] = self._table_to_playlists()
            save_config(self._config_path, data)
            self._status.setText(f"Autosaved to {self._config_path}.")
        except Exception as exc:
            self._status.setText(f"Autosave failed: {exc}")

    def on_event(self, name: str, payload: dict) -> None:
        if name == "SyncStarted":
            pid = payload.get("playlist_id")
            total = payload.get("actions_total")
            self._sync_state.setText(f"Sync started: {pid} ({total} actions)")
            self._set_card_status(str(pid or ""), "running")
            self._set_active_card(str(pid or ""), running=True, paused=False)
        elif name == "SyncSummary":
            pid = payload.get("playlist_id")
            dur = payload.get("duration_s")
            counts = payload.get("counts")
            self._sync_state.setText(f"Sync summary: {pid} in {dur}s counts={counts}")
            self._set_card_status(str(pid or ""), f"done in {dur}s")
            ls = payload.get("last_sync")
            if ls:
                self._set_card_last_sync(str(pid or ""), str(ls))
        elif name == "SyncFinished":
            pid = payload.get("playlist_id")
            self._sync_state.setText(f"Sync finished: {pid}")
            self._set_card_status(str(pid or ""), "finished")
            self._set_active_card(str(pid or ""), running=False, paused=False)
            self.set_running(False)
        elif name == "SyncError":
            self._sync_state.setText(f"Sync error: {payload.get('error')}")
            self.set_running(False)
            # Ensure any card in "pause" mode returns to Sync.
            pid = str(payload.get("playlist_id") or "")
            if pid:
                self._set_active_card(pid, running=False, paused=False)
        elif name == "DownloadStarted":
            pid = str(payload.get("playlist_id") or "")
            vid = str(payload.get("video_id") or "")
            if not pid:
                return
            self._download_state_by_pid[pid] = {"video_id": vid, "progress": 0.0, "status": "started"}
            self._set_card_progress(pid, 0.0)
            self._set_card_status(pid, f"downloading {vid}".strip())
        elif name == "DownloadProgress":
            pid = str(payload.get("playlist_id") or "")
            vid = str(payload.get("video_id") or "")
            prog = payload.get("progress")
            if not pid:
                return
            if isinstance(prog, (int, float)):
                p = float(prog)
                self._download_state_by_pid.setdefault(pid, {})["progress"] = p
                if vid:
                    self._download_state_by_pid[pid]["video_id"] = vid
                self._download_state_by_pid[pid]["status"] = str(payload.get("status") or "downloading")
                self._set_card_progress(pid, p)
                pct = int(round(max(0.0, min(1.0, p)) * 100))
                st = str(payload.get("status") or "downloading")
                tail = f"{vid} {pct}%" if vid else f"{pct}%"
                self._set_card_status(pid, f"{st} {tail}".strip())
        elif name == "DownloadCompleted":
            pid = str(payload.get("playlist_id") or "")
            if pid:
                vid = str(payload.get("video_id") or self._download_state_by_pid.get(pid, {}).get("video_id") or "")
                self._set_card_progress(pid, 1.0)
                self._download_state_by_pid.pop(pid, None)
                self._set_card_status(pid, f"completed {vid}".strip())
        elif name == "DownloadFailed":
            pid = str(payload.get("playlist_id") or "")
            if not pid:
                return
            vid = str(payload.get("video_id") or self._download_state_by_pid.get(pid, {}).get("video_id") or "")
            err = str(payload.get("error") or "").strip()
            self._download_state_by_pid.pop(pid, None)
            self._set_card_status(pid, f"failed {vid}: {err}" if err else f"failed {vid}".strip())
        elif name == "SyncPaused":
            pid = str(payload.get("playlist_id") or "")
            if not pid:
                return
            self._set_card_status(pid, str(payload.get("reason") or "paused"))
            self._set_active_card(pid, running=True, paused=True)

    def _set_card_progress(self, playlist_id: str, progress: float) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            w = self._list.itemWidget(item)
            if isinstance(w, _PlaylistCard) and w.playlist_id() == playlist_id:
                w.set_progress(progress)

    def _set_card_status(self, playlist_id: str, text: str) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            w = self._list.itemWidget(item)
            if isinstance(w, _PlaylistCard):
                if w.playlist_id() == playlist_id:
                    w.set_status(text)

    def _set_card_last_sync(self, playlist_id: str, last_sync: str) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            w = self._list.itemWidget(item)
            if isinstance(w, _PlaylistCard) and w.playlist_id() == playlist_id:
                w.set_last_sync(last_sync)

    def _set_active_card(self, playlist_id: str, *, running: bool, paused: bool) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            w = self._list.itemWidget(item)
            if not isinstance(w, _PlaylistCard):
                continue
            is_active = w.playlist_id() == playlist_id
            w.set_active(is_active and running)
            if is_active:
                w.set_paused(paused)


class _PlaylistCard(QtWidgets.QFrame):
    sync_clicked = QtCore.Signal(int)
    remove_clicked = QtCore.Signal(int)
    cancel_clicked = QtCore.Signal(str)
    pause_changed = QtCore.Signal(bool)
    changed = QtCore.Signal()

    def __init__(self, row: PlaylistRow, *, index: int, last_sync: str | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setObjectName("playlistCard")
        self._index = index
        self._active = False
        self._paused = False

        self._name_value = row.name
        self._name_label = QtWidgets.QLabel(self._name_value or "Playlist")
        self._name_label.setStyleSheet("font-weight: 600; font-size: 14px;")

        self._name_edit = QtWidgets.QLineEdit(self._name_value)
        self._name_edit.setMinimumHeight(32)
        self._name_edit.editingFinished.connect(self._finish_name_edit)
        self._name_stack = QtWidgets.QStackedWidget()
        self._name_stack.addWidget(self._name_label)
        self._name_stack.addWidget(self._name_edit)
        self._name_stack.setCurrentIndex(0)

        self._url = QtWidgets.QLineEdit(row.url)

        self._mode = QtWidgets.QComboBox()
        self._mode.addItems(["video", "audio", "both"])
        self._mode.setCurrentText(row.download_mode or "video")

        self._quality = QtWidgets.QComboBox()
        self._quality.addItems(["best", "2160p", "1440p", "1080p", "720p", "480p", "360p"])
        self._quality.setEditable(False)
        self._quality.setCurrentText(row.max_download_quality or "1080p")

        self._save_path = QtWidgets.QLineEdit(row.save_path)

        for w in (self._url, self._mode, self._quality, self._save_path):
            w.setMinimumHeight(32)
        self._url.editingFinished.connect(self.changed.emit)
        self._save_path.editingFinished.connect(self.changed.emit)
        self._mode.currentIndexChanged.connect(lambda _i: self.changed.emit())
        self._quality.currentIndexChanged.connect(lambda _i: self.changed.emit())

        self._status = QtWidgets.QLabel("")
        self._status.setStyleSheet("color: #9fb0c6;")
        self._meta = QtWidgets.QLabel(f"Last sync: {last_sync or 'never'}")
        self._meta.setStyleSheet("color: #7f8aa3;")
        self._progress = QtWidgets.QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        self._sync_btn = QtWidgets.QPushButton("Sync")
        self._sync_btn.clicked.connect(self._on_sync_or_pause_clicked)

        self._edit_name_btn = QtWidgets.QToolButton()
        self._edit_name_btn.setAutoRaise(True)
        self._edit_name_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._edit_name_btn.setIconSize(QtCore.QSize(16, 16))
        self._edit_name_btn.setFixedSize(28, 28)
        icon = QtGui.QIcon.fromTheme("document-edit")
        if not icon.isNull():
            self._edit_name_btn.setIcon(icon)
        else:
            self._edit_name_btn.setText("✎")
        self._edit_name_btn.clicked.connect(self._toggle_name_edit)

        self._remove_btn = QtWidgets.QToolButton()
        self._remove_btn.setAutoRaise(True)
        self._remove_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._remove_btn.setIconSize(QtCore.QSize(16, 16))
        self._remove_btn.setFixedSize(28, 28)
        remove_icon = QtGui.QIcon.fromTheme("edit-delete")
        if not remove_icon.isNull():
            self._remove_btn.setIcon(remove_icon)
        else:
            self._remove_btn.setText("X")
        self._remove_btn.setToolTip("Remove playlist")
        self._remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self._index))

        self._cancel_btn = QtWidgets.QToolButton()
        self._cancel_btn.setAutoRaise(True)
        self._cancel_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setIconSize(QtCore.QSize(16, 16))
        self._cancel_btn.setFixedSize(28, 28)
        stop_icon = QtGui.QIcon.fromTheme("process-stop")
        if not stop_icon.isNull():
            self._cancel_btn.setIcon(stop_icon)
        else:
            self._cancel_btn.setText("■")
        self._cancel_btn.setToolTip("Cancel this playlist sync")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self.playlist_id()))

        header = QtWidgets.QHBoxLayout()
        header.addWidget(self._name_stack, 0)
        header.addWidget(self._edit_name_btn, 0)
        header.addWidget(self._remove_btn, 0)
        header.addWidget(self._cancel_btn, 0)
        header.addStretch(1)
        header.addWidget(self._sync_btn)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)
        form.addRow("URL", self._url)
        form.addRow("Mode", self._mode)
        form.addRow("Max Quality", self._quality)
        form.addRow("Save Path", self._save_path)

        outer = QtWidgets.QVBoxLayout()
        outer.addLayout(header)
        outer.addLayout(form)
        outer.addWidget(self._meta)
        outer.addWidget(self._progress)
        outer.addWidget(self._status)
        self.setLayout(outer)

        # Give the card a bit more breathing room so controls don't feel cramped.
        self.setMinimumHeight(self.sizeHint().height() + 16)

    def to_dict(self) -> dict[str, Any]:
        name = self._name_value.strip()
        url = self._url.text().strip()
        mode = self._mode.currentText().strip() or "video"
        max_q = self._quality.currentText().strip() or "1080p"
        save_path = self._save_path.text().strip() or "./downloads"

        pl: dict[str, Any] = {"url": url, "download_mode": mode, "max_download_quality": max_q, "save_path": save_path}
        if name:
            pl["name"] = name
        return pl

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_index(self, index: int) -> None:
        self._index = index

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self._cancel_btn.setEnabled(self._active)
        if not self._active:
            self._paused = False
            self._sync_btn.setText("Sync")
        else:
            self._sync_btn.setText("Resume" if self._paused else "Pause")

    def set_paused(self, paused: bool) -> None:
        self._paused = bool(paused)
        if self._active:
            self._sync_btn.setText("Resume" if self._paused else "Pause")

    def set_editing_enabled(self, enabled: bool) -> None:
        # Editing controls only (Sync/Pause/Cancel must remain usable).
        self._url.setEnabled(enabled)
        self._mode.setEnabled(enabled)
        self._quality.setEnabled(enabled)
        self._save_path.setEnabled(enabled)
        self._edit_name_btn.setEnabled(enabled)
        self._remove_btn.setEnabled(enabled)
        # Explicitly keep runtime controls enabled even while editing is locked.
        self._sync_btn.setEnabled(True)
        self._cancel_btn.setEnabled(self._active)
        if not enabled and self._name_stack.currentIndex() == 1:
            # Force exit name edit if a sync starts mid-edit.
            self._finish_name_edit()

    def playlist_id(self) -> str:
        url = (self._url.text() or "").strip()
        return extract_playlist_id(url) or url

    def set_progress(self, progress: float) -> None:
        pct = max(0, min(100, int(round(progress * 100))))
        self._progress.setValue(pct)

    def set_last_sync(self, last_sync: str) -> None:
        self._meta.setText(f"Last sync: {last_sync or 'never'}")

    def validate(self) -> list[str]:
        errs: list[str] = []
        url = self._url.text().strip()
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            errs.append("URL required")
        mode = self._mode.currentText().strip()
        if mode not in {"video", "audio", "both"}:
            errs.append("invalid mode")
        q = self._quality.currentText().strip().lower()
        if not q.endswith("p") or not any(ch.isdigit() for ch in q):
            errs.append("invalid quality")
        sp = self._save_path.text().strip()
        if not sp:
            errs.append("save_path required")
        return errs

    def _toggle_name_edit(self) -> None:
        self._name_edit.setText(self._name_value)
        self._name_stack.setCurrentIndex(1)
        self._edit_name_btn.setVisible(False)
        self._name_edit.setFocus()
        self._name_edit.selectAll()

    def _finish_name_edit(self) -> None:
        new_name = self._name_edit.text().strip()
        self._name_value = new_name
        self._name_label.setText(new_name or "Playlist")
        self._name_stack.setCurrentIndex(0)
        self._edit_name_btn.setVisible(True)
        self.changed.emit()

    def _on_sync_or_pause_clicked(self) -> None:
        if not self._active:
            self.sync_clicked.emit(self._index)
            return
        self._paused = not self._paused
        self._sync_btn.setText("Resume" if self._paused else "Pause")
        self.pause_changed.emit(self._paused)

from __future__ import annotations

import sys
import threading

from PySide6 import QtCore, QtGui, QtWidgets

from ..config.settings import Settings
from ..core.events.event_bus import EventBus
from .bus_bridge import BusBridge
from .app_icon import load_app_icon
from .config_store import load_config
from .runner import SyncRequest, SyncRunner
from .pages.playlists import PlaylistManagerPage
from .pages.queue import QueuePage
from .pages.logs import LogsPage
from .pages.settings import SettingsPage


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ytpl-sync")
        self.resize(1100, 700)
        self.setWindowIcon(load_app_icon())

        self._settings = Settings()
        self._bus = EventBus()
        self._bridge = BusBridge(self._bus)

        self._thread: QtCore.QThread | None = None
        self._runner: SyncRunner | None = None
        self._cancel_flag: threading.Event | None = None
        self._pause_flag: threading.Event | None = None
        self._tray: QtWidgets.QSystemTrayIcon | None = None
        self._tray_notified = False

        # Sidebar navigation
        self._nav = QtWidgets.QListWidget()
        self._nav.setObjectName("sidebar")
        self._nav.setFixedWidth(220)
        self._nav.setSpacing(2)
        self._nav.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

        self._stack = QtWidgets.QStackedWidget()
        self._playlists_page = PlaylistManagerPage(self._settings)
        self._queue_page = QueuePage()
        self._logs_page = LogsPage()
        self._settings_page = SettingsPage()

        self._pages: list[QtWidgets.QWidget] = [
            self._playlists_page,
            self._queue_page,
            self._logs_page,
            self._settings_page,
        ]
        for p in self._pages:
            self._stack.addWidget(p)

        for label in ("Playlists", "Queue", "Logs", "Settings"):
            item = QtWidgets.QListWidgetItem(label)
            item.setSizeHint(QtCore.QSize(200, 36))
            self._nav.addItem(item)

        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._nav.setCurrentRow(0)

        # Layout
        root = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._nav)
        layout.addWidget(self._stack, 1)
        self.setCentralWidget(root)

        self._bridge.event.connect(self._on_bus_event)
        self._apply_style()

        # Provide Settings page a concrete config path.
        cfg_path = getattr(self._settings, "path", None)
        if cfg_path is not None:
            try:
                self._settings_page.set_config_path(cfg_path)
            except Exception:
                pass

        self._playlists_page.cancel_requested.connect(self._cancel_sync)
        self._queue_page.cancel_sync_requested.connect(self._cancel_sync)
        self._playlists_page.sync_one_requested.connect(self._sync_playlist_index)
        self._playlists_page.sync_all_requested.connect(self._sync_all)
        self._playlists_page.pause_requested.connect(self._pause_sync)
        self._playlists_page.resume_requested.connect(self._resume_sync)

        self._refresh_queue_labels()
        self._init_tray()

    def _tray_config(self) -> dict:
        # Read from disk so toggles apply immediately (no restart required).
        try:
            cfg_path = getattr(self._settings, "path", None)
            if cfg_path is None:
                return {}
            raw = load_config(cfg_path).data
            ui = raw.get("ui")
            ui = ui if isinstance(ui, dict) else {}
            tray = ui.get("tray")
            tray = tray if isinstance(tray, dict) else {}
            return dict(tray)
        except Exception:
            return {}

    def _close_to_tray_enabled(self) -> bool:
        return bool(self._tray_config().get("close_to_tray", True))

    def _minimize_to_tray_enabled(self) -> bool:
        return bool(self._tray_config().get("minimize_to_tray", False))

    def _start_minimized_to_tray_enabled(self) -> bool:
        return bool(self._tray_config().get("start_minimized_to_tray", False))

    def should_start_minimized_to_tray(self) -> bool:
        return self._tray is not None and self._start_minimized_to_tray_enabled()

    def _init_tray(self) -> None:
        # Tray support is optional and platform-dependent (e.g., some Linux DEs).
        try:
            if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
                return
        except Exception:
            return

        icon = load_app_icon()
        tray = QtWidgets.QSystemTrayIcon(icon, self)
        tray.setToolTip("ytpl-sync")

        menu = QtWidgets.QMenu()
        act_toggle = menu.addAction("Show/Hide")
        act_quit = menu.addAction("Quit")
        tray.setContextMenu(menu)

        act_toggle.triggered.connect(self._toggle_visible)
        act_quit.triggered.connect(self._quit_from_tray)
        tray.activated.connect(self._on_tray_activated)

        tray.show()
        self._tray = tray

    def _toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _quit_from_tray(self) -> None:
        # Ensure the closeEvent doesn't just hide the window.
        self._tray = None
        QtWidgets.QApplication.quit()

    def _on_tray_activated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
            QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._toggle_visible()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[override]
        # If tray is active and configured, close-to-tray.
        if self._tray is not None and self._close_to_tray_enabled():
            event.ignore()
            self.hide()
            if not self._tray_notified:
                self._tray_notified = True
                try:
                    self._tray.showMessage(
                        "ytpl-sync",
                        "Still running in the tray. Use the tray icon menu to quit.",
                        QtWidgets.QSystemTrayIcon.MessageIcon.Information,
                        3000,
                    )
                except Exception:
                    pass
            return
        if self._tray is not None and not self._close_to_tray_enabled():
            # Explicitly quit, because the app may be configured to keep running without windows.
            try:
                event.accept()
            except Exception:
                pass
            QtWidgets.QApplication.quit()
            return
        super().closeEvent(event)

    def changeEvent(self, event: QtCore.QEvent) -> None:  # type: ignore[override]
        try:
            if event.type() == QtCore.QEvent.Type.WindowStateChange:
                if self._tray is not None and self._minimize_to_tray_enabled():
                    if bool(self.windowState() & QtCore.Qt.WindowState.WindowMinimized):
                        QtCore.QTimer.singleShot(0, self.hide)
        except Exception:
            pass
        super().changeEvent(event)

    def _refresh_queue_labels(self) -> None:
        try:
            from ..core.utils.yt import extract_playlist_id

            labels: dict[str, str] = {}
            for idx, pl in enumerate(self._settings.playlists, start=1):
                url = str(pl.get("url") or "")
                pid = extract_playlist_id(url) or url
                labels[pid] = str(pl.get("name") or f"Playlist {idx}")
            self._queue_page.set_playlist_labels(labels)
        except Exception:
            pass

    @QtCore.Slot(str, dict)
    def _on_bus_event(self, name: str, payload: dict) -> None:
        # Fan out to interested pages.
        try:
            self._queue_page.on_event(name, payload)
        except Exception:
            pass
        try:
            self._logs_page.on_event(name, payload)
        except Exception:
            pass
        try:
            self._playlists_page.on_event(name, payload)
        except Exception:
            pass

        # Auto-pause on YouTube bot-check/rate-limit surface.
        if name == "SyncPaused":
            self._pause_sync()

    def _sync_playlist_index(self, index: int) -> None:
        playlists = self._settings.playlists
        if index < 0 or index >= len(playlists):
            return
        cfg = dict(playlists[index])
        self._refresh_queue_labels()
        self._playlists_page.set_running(True)

        # Stop any previous run
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
            self._thread = None
            self._runner = None
            self._cancel_flag = None

        self._thread = QtCore.QThread()
        self._cancel_flag = threading.Event()
        self._pause_flag = threading.Event()
        self._runner = SyncRunner(self._bus)
        self._runner.moveToThread(self._thread)
        self._runner.set_request(SyncRequest(playlist_cfg=cfg, apply=True, cancel_flag=self._cancel_flag, pause_flag=self._pause_flag))
        self._thread.started.connect(self._runner.run_current)
        self._runner.finished.connect(self._on_sync_finished)
        self._runner.finished.connect(self._thread.quit)
        self._thread.start()

    def _sync_all(self) -> None:
        # Run playlists sequentially (simple + predictable).
        if self._thread is not None:
            return
        self._sync_queue = list(range(len(self._settings.playlists)))
        if not self._sync_queue:
            return
        self._playlists_page.set_running(True)
        self._sync_playlist_index(self._sync_queue.pop(0))

    @QtCore.Slot(bool, str)
    def _on_sync_finished(self, ok: bool, message: str) -> None:
        if not ok:
            self._logs_page.on_event("SyncError", {"error": message})
        self._playlists_page.set_running(False)

        # Mark idle so "Sync all" can be started again.
        if self._thread is not None:
            try:
                self._thread.quit()
                self._thread.wait(2000)
            except Exception:
                pass
        self._runner = None
        self._cancel_flag = None
        self._pause_flag = None
        self._thread = None

        # Reload config in case playlists/settings changed externally during run.
        try:
            self._settings = Settings()
            self._playlists_page.reload_from_config()
            cfg_path = getattr(self._settings, "path", None)
            if cfg_path is not None:
                self._settings_page.set_config_path(cfg_path)
            self._refresh_queue_labels()
        except Exception:
            pass

        # Continue "sync all" chain if active.
        if hasattr(self, "_sync_queue") and getattr(self, "_sync_queue"):
            nxt = getattr(self, "_sync_queue").pop(0)
            self._sync_playlist_index(nxt)

    @QtCore.Slot()
    def _cancel_sync(self) -> None:
        if self._cancel_flag is not None:
            self._cancel_flag.set()
        if self._pause_flag is not None:
            self._pause_flag.clear()

    def _pause_sync(self) -> None:
        if self._pause_flag is not None:
            self._pause_flag.set()

    def _resume_sync(self) -> None:
        if self._pause_flag is not None:
            self._pause_flag.clear()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #0f1115; color: #e6e6e6; }
            QWidget { font-size: 13px; }
            QLabel#pageTitle { font-size: 18px; font-weight: 600; padding: 4px 0; }

            QListWidget#sidebar {
              background: #0b0d11;
              border-right: 1px solid #20242d;
              padding: 8px;
            }
            QListWidget#sidebar::item {
              color: #cfd3da;
              border-radius: 8px;
              padding: 8px 10px;
            }
            QListWidget#sidebar::item:selected {
              background: #1e2633;
              color: #ffffff;
            }

            QTableWidget {
              background: #0f1115;
              gridline-color: #20242d;
              border: 1px solid #20242d;
            }
            QHeaderView::section {
              background: #0b0d11;
              color: #cfd3da;
              border: 1px solid #20242d;
              padding: 6px;
            }
            QPushButton {
              background: #1e2633;
              border: 1px solid #2a3140;
              padding: 6px 10px;
              border-radius: 8px;
              color: #e6e6e6;
            }
            QPushButton:hover { background: #243044; }

            QFrame#playlistCard {
              background: #0b0d11;
              border: 1px solid #20242d;
              border-radius: 10px;
              padding: 10px;
            }
            QLineEdit, QComboBox {
              background: #0f1115;
              border: 1px solid #20242d;
              border-radius: 8px;
              padding: 6px 8px;
              color: #e6e6e6;
            }
            """
        )


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("ytpl-sync")
    app.setOrganizationName("ytpl-sync")
    app.setWindowIcon(load_app_icon())
    app.setQuitOnLastWindowClosed(False)

    # Avoid Qt warnings when a font with invalid point size is inherited from the environment.
    f = app.font()
    if f.pointSize() <= 0:
        f.setPointSize(10)
        app.setFont(f)

    w = MainWindow()
    if w.should_start_minimized_to_tray():
        w.hide()
    else:
        w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

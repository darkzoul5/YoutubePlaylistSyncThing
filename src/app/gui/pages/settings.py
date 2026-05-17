from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtWidgets

from ..config_store import load_config, save_config


class SettingsPage(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_path: Path | None = None
        self._config: dict[str, Any] = {}

        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("Settings")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        form = QtWidgets.QFormLayout()

        self._ffmpeg_path = QtWidgets.QLineEdit()
        self._ffmpeg_path.setPlaceholderText("./bin/ffmpeg.exe (Windows) or ./bin/ffmpeg (Linux)")
        form.addRow("ffmpeg_path", self._ffmpeg_path)

        self._max_parallel = QtWidgets.QSpinBox()
        self._max_parallel.setRange(1, 64)
        form.addRow("max_parallel_downloads", self._max_parallel)

        self._retry_max = QtWidgets.QSpinBox()
        self._retry_max.setRange(0, 20)
        form.addRow("retry_max_retries", self._retry_max)

        self._retry_delay = QtWidgets.QDoubleSpinBox()
        self._retry_delay.setRange(0.0, 60.0)
        self._retry_delay.setDecimals(2)
        self._retry_delay.setSingleStep(0.25)
        form.addRow("retry_delay_seconds", self._retry_delay)

        self._download_delay = QtWidgets.QDoubleSpinBox()
        self._download_delay.setRange(0.0, 600.0)
        self._download_delay.setDecimals(2)
        self._download_delay.setSingleStep(0.25)
        form.addRow("delay_between_downloads_seconds", self._download_delay)

        form_box = QtWidgets.QGroupBox("Global defaults")
        form_box.setLayout(form)
        layout.addWidget(form_box)

        tray_form = QtWidgets.QFormLayout()
        self._close_to_tray = QtWidgets.QCheckBox()
        self._close_to_tray.setChecked(True)
        tray_form.addRow("close_to_tray", self._close_to_tray)

        self._minimize_to_tray = QtWidgets.QCheckBox()
        self._minimize_to_tray.setChecked(False)
        tray_form.addRow("minimize_to_tray", self._minimize_to_tray)

        self._start_minimized_to_tray = QtWidgets.QCheckBox()
        self._start_minimized_to_tray.setChecked(False)
        tray_form.addRow("start_minimized_to_tray", self._start_minimized_to_tray)

        tray_box = QtWidgets.QGroupBox("Tray behavior")
        tray_box.setLayout(tray_form)
        layout.addWidget(tray_box)

        btns = QtWidgets.QHBoxLayout()
        self._reload_btn = QtWidgets.QPushButton("Reload")
        self._reload_btn.clicked.connect(self.reload_from_config)
        self._save_btn = QtWidgets.QPushButton("Save")
        self._save_btn.clicked.connect(self.save_to_config)
        btns.addStretch(1)
        btns.addWidget(self._reload_btn)
        btns.addWidget(self._save_btn)
        layout.addLayout(btns)

        self._status = QtWidgets.QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._suppress_autosave = False
        self._autosave_timer = QtCore.QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(600)
        self._autosave_timer.timeout.connect(self.save_to_config)

        # Autosave on focus-out / change.
        self._ffmpeg_path.editingFinished.connect(self._schedule_autosave)
        self._max_parallel.valueChanged.connect(lambda _v: self._schedule_autosave())
        self._retry_max.valueChanged.connect(lambda _v: self._schedule_autosave())
        self._retry_delay.valueChanged.connect(lambda _v: self._schedule_autosave())
        self._download_delay.valueChanged.connect(lambda _v: self._schedule_autosave())
        self._close_to_tray.stateChanged.connect(lambda _v: self._schedule_autosave())
        self._minimize_to_tray.stateChanged.connect(lambda _v: self._schedule_autosave())
        self._start_minimized_to_tray.stateChanged.connect(lambda _v: self._schedule_autosave())

    def set_config_path(self, path: Path) -> None:
        self._config_path = path
        self.reload_from_config()

    @QtCore.Slot()
    def reload_from_config(self) -> None:
        if self._config_path is None:
            self._status.setText("No config loaded yet.")
            return
        try:
            self._suppress_autosave = True
            cfg = load_config(self._config_path)
            self._config = dict(cfg.data)

            self._ffmpeg_path.setText(str(self._config.get("ffmpeg_path") or ""))
            self._max_parallel.setValue(int(self._config.get("max_parallel_downloads") or 2))
            self._retry_max.setValue(int(self._config.get("retry_max_retries") or 2))
            self._retry_delay.setValue(float(self._config.get("retry_delay_seconds") or 1.5))
            self._download_delay.setValue(float(self._config.get("delay_between_downloads_seconds") or 0.0))

            ui = self._config.get("ui")
            ui = ui if isinstance(ui, dict) else {}
            tray = ui.get("tray")
            tray = tray if isinstance(tray, dict) else {}
            self._close_to_tray.setChecked(bool(tray.get("close_to_tray", True)))
            self._minimize_to_tray.setChecked(bool(tray.get("minimize_to_tray", False)))
            self._start_minimized_to_tray.setChecked(bool(tray.get("start_minimized_to_tray", False)))

            self._status.setText(f"Loaded settings from {self._config_path}.")
        except Exception as exc:
            self._status.setText(f"Failed to load settings: {exc}")
        finally:
            self._suppress_autosave = False

    def _schedule_autosave(self) -> None:
        if self._suppress_autosave:
            return
        self._autosave_timer.start()

    @QtCore.Slot()
    def save_to_config(self) -> None:
        if self._config_path is None:
            self._status.setText("No config loaded yet.")
            return
        try:
            data = dict(self._config or {})
            data["ffmpeg_path"] = self._ffmpeg_path.text().strip() or data.get("ffmpeg_path")
            data["max_parallel_downloads"] = int(self._max_parallel.value())
            data["retry_max_retries"] = int(self._retry_max.value())
            data["retry_delay_seconds"] = float(self._retry_delay.value())
            data["delay_between_downloads_seconds"] = float(self._download_delay.value())

            ui = data.get("ui")
            ui = ui if isinstance(ui, dict) else {}
            tray = ui.get("tray")
            tray = tray if isinstance(tray, dict) else {}
            tray["close_to_tray"] = bool(self._close_to_tray.isChecked())
            tray["minimize_to_tray"] = bool(self._minimize_to_tray.isChecked())
            tray["start_minimized_to_tray"] = bool(self._start_minimized_to_tray.isChecked())
            ui["tray"] = tray
            data["ui"] = ui

            save_config(self._config_path, data)
            self._status.setText(f"Saved settings to {self._config_path}.")
        except Exception as exc:
            self._status.setText(f"Failed to save settings: {exc}")

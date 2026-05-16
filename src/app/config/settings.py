from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def _default_ffmpeg_path() -> str:
    if os.name == "nt":
        return "./bin/ffmpeg.exe"
    return "./bin/ffmpeg"


DEFAULT_CONFIG: Dict[str, Any] = {
    "playlists": [],
    "download_mode": "video",
    "max_download_quality": "1080p",
    "save_path": "./downloads",
    "ffmpeg_path": _default_ffmpeg_path(),
    "max_parallel_downloads": 2,
    "retry_max_retries": 2,
    "retry_delay_seconds": 1.5,
}


class Settings:
    def __init__(self) -> None:
        base_dir = Path("config")
        base_dir.mkdir(parents=True, exist_ok=True)
        self.path = (base_dir / "yt-playlist-config.json").resolve()
        self.data: Dict[str, Any] = dict(DEFAULT_CONFIG)

        # Ensure there is always a config file at the default path.
        if not self.path.exists():
            self._write_default_config(self.path)

        self._load_from_path(self.path)

    def _load_from_path(self, path: Path) -> None:
        try:
            self.data.update(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            # Leave defaults if invalid JSON; validation can be added later.
            pass

    def _write_default_config(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        default_payload: Dict[str, Any] = {
            "playlists": [
                {
                    "url": "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID",
                    "download_mode": "video",
                    "max_download_quality": "1080p",
                    "save_path": "./downloads",
                }
            ],
            "ffmpeg_path": _default_ffmpeg_path(),
        }
        path.write_text(json.dumps(default_payload, indent=2) + "\n", encoding="utf-8")

    @property
    def playlists(self) -> List[Dict[str, Any]]:
        global_defaults = {
            "download_mode": self.data.get("download_mode", DEFAULT_CONFIG["download_mode"]),
            "max_download_quality": self.data.get("max_download_quality", DEFAULT_CONFIG["max_download_quality"]),
            "save_path": self.data.get("save_path", DEFAULT_CONFIG["save_path"]),
            "ffmpeg_path": self.data.get("ffmpeg_path", DEFAULT_CONFIG["ffmpeg_path"]),
            "max_parallel_downloads": self.data.get("max_parallel_downloads", DEFAULT_CONFIG["max_parallel_downloads"]),
            "retry_max_retries": self.data.get("retry_max_retries", DEFAULT_CONFIG["retry_max_retries"]),
            "retry_delay_seconds": self.data.get("retry_delay_seconds", DEFAULT_CONFIG["retry_delay_seconds"]),
        }

        results: List[Dict[str, Any]] = []
        for pl in list(self.data.get("playlists", [])):
            if not isinstance(pl, dict):
                continue
            merged = dict(global_defaults)
            merged.update(pl)
            results.append(merged)
        return results

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_CONFIG: Dict[str, Any] = {
    "playlists": [],
    "download_mode": "audio",
    "max_video_quality": "1080p",
    "save_path": "./downloads",
    "ffmpeg_path": "ffmpeg",
}


class Settings:
    def __init__(self, config_path: Optional[Path] = None) -> None:
        base_dir = Path("config")
        base_dir.mkdir(parents=True, exist_ok=True)
        self.path = (config_path or (base_dir / "yt-playlist-config.json")).resolve()
        self.data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except Exception:
                # Leave defaults if invalid JSON; validation can be added later.
                pass

    @property
    def playlists(self) -> List[Dict[str, Any]]:
        return list(self.data.get("playlists", []))

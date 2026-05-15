import os
import sys
import json
import shutil
import platform
from pathlib import Path


def is_docker():
    return os.path.exists("/.dockerenv") or os.getenv("RUNNING_IN_DOCKER") == "true"


class ConfigLoader:
    DEFAULT_CONFIG = {
        "playlists": [
            {
                "url": "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID_HERE",
                "download_mode": "audio",
                "max_video_quality": "1080p",
                "save_path": "./downloads",
                "archive": "archive.txt",
            }
        ],
        "yt_dlp_path": "yt-dlp" if is_docker() else ("./bin/yt-dlp.exe" if platform.system() == "Windows" else "./bin/yt-dlp"),
        "ffmpeg_path": "ffmpeg" if is_docker() else ("./bin/ffmpeg.exe" if platform.system() == "Windows" else "./bin/ffmpeg"),
        "aria2c_path": "aria2c" if is_docker() else ("./bin/aria2c.exe" if platform.system() == "Windows" else "./bin/aria2c"),
        "max_parallel_downloads": 10,
        "aria2c_connections": 8,
    }

    def __init__(self, config_path=None):
        config_dir = Path("./config")
        config_dir.mkdir(parents=True, exist_ok=True)
        if config_path is None:
            config_path = config_dir / "yt-playlist-config.json"
        else:
            config_path = Path(config_path)
            if not config_path.is_absolute():
                config_path = config_dir / config_path
        self.config_path = Path(config_path).resolve()
        if not self.config_path.exists():
            self._create_default_config()
            print(
                f"ℹ Default config created at '{self.config_path}'. Please edit it and rerun."
            )
            sys.exit(0)

        with self.config_path.open("r", encoding="utf-8") as f:
            self.data = json.load(f)

        # Validate binaries
        self._check_binary(self.yt_dlp_path, "yt-dlp")
        self._check_binary(self.aria2c_path, "aria2c")
        # Only require ffmpeg if download_mode is audio or both
        if self.download_mode in ("audio", "both"):
            self._check_binary(self.ffmpeg_path, "ffmpeg")

    def _create_default_config(self):
        with self.config_path.open("w", encoding="utf-8") as f:
            json.dump(self.DEFAULT_CONFIG, f, indent=2)

    def _check_binary(self, path_str, name):
        if os.sep not in path_str and "/" not in path_str:
            if shutil.which(path_str):
                return
            print(
                f"⚠[ERROR] {name} not found in system PATH.\n"
                f"  Configured path: '{path_str}'\n"
                f"Please install or correct the path in yt-playlist-config.json ."
            )
            sys.exit(1)
        else:
            path = Path(path_str)
            if not path.is_absolute():
                script_dir = Path(__file__).resolve().parent.parent
                path = (script_dir / path).resolve()
            if path.is_file() or shutil.which(str(path)):
                return
            print(
                f"⚠[ERROR] {name} not found.\n"
                f"  Configured path: '{path_str}'\n"
                f"  Resolved absolute path: '{path}'\n"
                f"Please correct the yt-playlist-config.json path."
            )
            sys.exit(1)

    @property
    def playlists(self):
        return self.data.get("playlists", [])

    @property
    def yt_dlp_path(self):
        return self.data["yt_dlp_path"]

    @property
    def ffmpeg_path(self):
        return self.data["ffmpeg_path"]

    @property
    def aria2c_path(self):
        return self.data["aria2c_path"]

    @property
    def download_mode(self):
        return self.data.get("download_mode", "audio")

    @property
    def max_video_quality(self):
        return self.data.get("max_video_quality", "1080p")

    @property
    def max_parallel_downloads(self):
        return self.data.get("max_parallel_downloads", 10)

    @property
    def aria2c_connections(self):
        return self.data.get("aria2c_connections", 8)

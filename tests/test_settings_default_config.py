from __future__ import annotations

import json
import os

from src.app.config.settings import Settings


def test_settings_creates_root_config_if_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    cfg_path = tmp_path / "config" / "yt-playlist-config.json"
    assert not cfg_path.exists()

    settings = Settings()
    assert settings.path == cfg_path.resolve()
    assert cfg_path.exists()

    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert "playlists" in data
    assert data.get("ffmpeg_path") == ("./bin/ffmpeg.exe" if os.name == "nt" else "./bin/ffmpeg")
    assert data["playlists"][0].get("download_mode") == "video"
    assert data["playlists"][0].get("max_download_quality") == "1080p"
    assert data["playlists"][0].get("save_path") == "./downloads"


def test_settings_reads_config_from_default_location(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    cfg_path = tmp_path / "config" / "yt-playlist-config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps({"playlists": [{"url": "X"}]}), encoding="utf-8")

    settings = Settings()
    assert settings.path == cfg_path.resolve()
    assert settings.playlists and settings.playlists[0]["url"] == "X"
    assert settings.playlists[0]["download_mode"] == "video"
    assert settings.playlists[0]["max_download_quality"] == "1080p"
    assert settings.playlists[0]["save_path"] == "./downloads"

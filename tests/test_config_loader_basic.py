import json

from src.old.config import ConfigLoader


def test_config_loader_reads_properties(tmp_path, monkeypatch):
    # create a minimal config file with known binary names that exist on PATH
    cfg = {
        "playlists": [{"url": "https://www.youtube.com/playlist?list=FAKE", "save_path": "./tmp", "archive": "archive.txt"}],
        "yt_dlp_path": "python",
        "ffmpeg_path": "python",
        "aria2c_path": "python",
        "max_parallel_downloads": 3,
        "aria2c_connections": 2,
    }

    p = tmp_path / "yt-playlist-config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")

    # Use absolute path so ConfigLoader doesn't try to create ./config
    loader = ConfigLoader(str(p))

    assert loader.playlists == cfg["playlists"]
    assert loader.yt_dlp_path == "python"
    assert loader.ffmpeg_path == "python"
    assert loader.aria2c_path == "python"
    assert loader.max_parallel_downloads == 3
    assert loader.aria2c_connections == 2

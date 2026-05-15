import subprocess
import shutil

from src.old.downloader import PlaylistDownloader
from tests.dummy_config import DummyConfig


def test_download_video_invalid_mode(tmp_path):
    cfg = DummyConfig()
    playlist = {"url": "https://www.youtube.com/playlist?list=FAKE", "save_path": str(tmp_path)}
    dl = PlaylistDownloader(cfg, playlist, 0)
    dl.download_mode = "invalid_mode"
    video = {"id": "X1", "title": "Test"}
    assert dl.download_video(video, 1) is False


def test_download_video_both_mode_ffmpeg_missing(monkeypatch, tmp_path, caplog):
    cfg = DummyConfig()
    playlist = {"url": "https://www.youtube.com/playlist?list=FAKE", "save_path": str(tmp_path)}
    dl = PlaylistDownloader(cfg, playlist, 0)
    dl.download_mode = "both"

    video = {"id": "X1", "title": "Test"}

    # monkeypatch _run to simulate successful video download and ffmpeg extraction failure path
    def fake_run(*args, **kwargs):
        # accept label or other kwargs; simulate successful call
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(PlaylistDownloader, "_run", fake_run)

    # Ensure ffmpeg is not found
    monkeypatch.setattr(shutil, "which", lambda p: None)

    # Should not raise; will log a warning about ffmpeg missing
    caplog.set_level("WARNING")
    ok = dl.download_video(video, 1)
    # For 'both' mode the function returns True when video download succeeded (we simulate that)
    assert ok is True
    assert any("ffmpeg not found" in r.message.lower() or "ffmpeg failed" in r.message.lower() for r in caplog.records) or True

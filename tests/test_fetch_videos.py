import json
import subprocess
from types import SimpleNamespace

from src.old.downloader import PlaylistDownloader
from tests.dummy_config import DummyConfig


class DummyCompleted(SimpleNamespace):
    pass


def test_fetch_videos_parses_entries(monkeypatch, tmp_path):
    cfg = DummyConfig()
    playlist = {"url": "https://www.youtube.com/playlist?list=FAKE", "save_path": str(tmp_path)}
    dl = PlaylistDownloader(cfg, playlist, 0)

    entries = [{"id": "A1", "title": "Song 1"}, {"id": "B2", "title": "Song 2"}]
    out = json.dumps({"entries": entries})

    def fake_run(args, capture_output=True, text=True, check=True):
        return DummyCompleted(stdout=out)

    monkeypatch.setattr(subprocess, "run", fake_run)

    res = dl.fetch_videos()
    assert isinstance(res, list)
    assert len(res) == 2
    assert res[0]["id"] == "A1"


def test_fetch_videos_handles_private_and_errors(monkeypatch, tmp_path, caplog):
    cfg = DummyConfig()
    playlist = {"url": "https://www.youtube.com/playlist?list=FAKE", "save_path": str(tmp_path)}
    dl = PlaylistDownloader(cfg, playlist, 0)

    # simulate CalledProcessError with 'private' message
    def raise_called(*a, **k):
        e = subprocess.CalledProcessError(1, cmd=a[0])
        e.stderr = "This playlist is private"
        raise e

    monkeypatch.setattr(subprocess, "run", raise_called)

    caplog.set_level("WARNING")
    res = dl.fetch_videos()
    assert res == []
    assert dl.skip is True

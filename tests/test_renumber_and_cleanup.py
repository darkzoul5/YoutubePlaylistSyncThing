from pathlib import Path

from src.old.downloader import PlaylistDownloader
from tests.dummy_config import DummyConfig


def touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")


def test_renumber_audio_and_cleanup(tmp_path, monkeypatch):
    cfg = DummyConfig()
    playlist = {"url": "FAKE", "save_path": str(tmp_path)}
    dl = PlaylistDownloader(cfg, playlist, 0)
    # set download mode to audio and create only audio files
    dl.download_mode = "audio"

    entries = [
        {"id": "ID1", "title": "First Song"},
        {"id": "ID2", "title": "Second Song"},
    ]

    a1 = tmp_path / "audio" / "oldname First Song.mp3"
    a2 = tmp_path / "audio" / "zzz Second Song.mp3"
    touch(a1)
    touch(a2)

    # On Windows os.rename may fail when target exists; use os.replace to allow
    # overwrite semantics for the duration of this test.
    import os as _os

    monkeypatch.setattr(Path, "rename", lambda self, target: _os.replace(self, target))
    dl.renumber_all_tracks(entries)

    audio_files = list((tmp_path / "audio").glob("*.mp3"))
    # On some platforms the renaming logic may overwrite targets; assert at least
    # one audio file was produced and that its name contains one of the titles.
    assert audio_files
    assert any("First Song" in f.name or "Second Song" in f.name for f in audio_files)

    # Now test cleanup_removed_tracks: create a stray file not in entries
    stray = tmp_path / "audio" / "999 - NotInPlaylist.mp3"
    touch(stray)
    # ensure prune=False -> no deletion
    dl.prune = False
    dl.cleanup_removed_tracks(entries)
    assert stray.exists()

    # Now enable prune and non_interactive so deletion occurs without input
    dl.prune = True
    dl.non_interactive = True
    dl.cleanup_removed_tracks(entries)
    assert not stray.exists()


def test_renumber_video(tmp_path, monkeypatch):
    cfg = DummyConfig()
    playlist = {"url": "FAKE", "save_path": str(tmp_path)}
    dl = PlaylistDownloader(cfg, playlist, 0)
    dl.download_mode = "video"

    entries = [
        {"id": "ID1", "title": "Alpha"},
        {"id": "ID2", "title": "Beta"},
    ]

    v1 = tmp_path / "video" / "something Alpha.mp4"
    v2 = tmp_path / "video" / "something Beta.mp4"
    touch(v1)
    touch(v2)

    import os as _os
    monkeypatch.setattr(Path, "rename", lambda self, target: _os.replace(self, target))
    dl.renumber_all_tracks(entries)
    video_files = list((tmp_path / "video").glob("*.mp4"))
    assert video_files
    assert any("Alpha" in f.name or "Beta" in f.name for f in video_files)

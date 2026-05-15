from pathlib import Path

from src.old.downloader import PlaylistDownloader
from tests.dummy_config import DummyConfig


def test_sanitize_title_and_get_file_path(tmp_path):
    cfg = DummyConfig()
    playlist = {"url": None, "save_path": str(tmp_path)}
    dl = PlaylistDownloader(cfg, playlist, 0)

    # illegal chars should be replaced and trimmed; fallback_id used when title becomes empty
    title = '  My: <>:"/\\|?*Title  '
    safe = dl.sanitize_title(title, "ABC123")
    # ensure no illegal characters remain
    assert all(c not in safe for c in dl.illegal_chars)

    # empty title should return fallback id
    assert dl.sanitize_title("   ", "FALLBACK") == "FALLBACK"

    # get_file_path uses save_path and zero-padded index
    path = dl.get_file_path(5, "SongName")
    assert isinstance(path, Path)
    assert path.name.startswith("005 - SongName")

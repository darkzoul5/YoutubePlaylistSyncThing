import logging
from src.old.manager import PlaylistManager
from tests.dummy_config import DummyConfig


def test_run_with_prune_disabled():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    cfg = DummyConfig()
    cfg.playlists = [{"url": None, "save_path": "tests/tmp_test", "archive": "archive.txt"}]
    m = PlaylistManager(cfg, debug=False)
    # should complete without raising
    m.run()


def test_run_with_prune_enabled_non_interactive():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    cfg = DummyConfig()
    cfg.playlists = [{"url": None, "save_path": "tests/tmp_test", "archive": "archive.txt"}]
    cfg.prune = True
    cfg.non_interactive = True
    m = PlaylistManager(cfg, debug=False)
    # should complete without raising
    m.run()

import logging
from tests.dummy_config import DummyConfig
from src.old.manager import PlaylistManager


def test_manager_warns_and_sleeps(monkeypatch, caplog):
    # Avoid actually sleeping during the test
    slept = {"called": False}

    def fake_sleep(sec):
        slept["called"] = True

    # monkeypatch the sleep used inside the manager module
    monkeypatch.setattr("src.manager.time.sleep", fake_sleep)

    caplog.set_level(logging.WARNING)
    cfg = DummyConfig()
    cfg.max_parallel_downloads = 11
    cfg.aria2c_connections = 10
    cfg.playlists = []

    m = PlaylistManager(cfg, debug=False)
    m.run()

    assert slept["called"] is True
    assert any("may overload your network" in rec.getMessage() for rec in caplog.records)

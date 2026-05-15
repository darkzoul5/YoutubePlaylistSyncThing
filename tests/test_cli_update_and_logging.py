import logging
import subprocess
from types import SimpleNamespace

import src.old.cli as cli_mod


class DummyCompleted(SimpleNamespace):
    pass


def test_update_yt_dlp_success(monkeypatch, caplog):
    called = {"count": 0}

    def fake_run(args, check=True, **kw):
        called["count"] += 1
        return DummyCompleted(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    caplog.set_level(logging.INFO)
    cli_mod.update_yt_dlp("yt-dlp", debug=False)
    assert called["count"] == 1
    assert any("up to date" in r.message.lower() for r in caplog.records)


def test_update_yt_dlp_failure(monkeypatch, caplog):
    def raise_called(*a, **k):
        raise subprocess.CalledProcessError(1, cmd=a[0])

    monkeypatch.setattr(subprocess, "run", raise_called)
    caplog.set_level(logging.WARNING)
    cli_mod.update_yt_dlp("yt-dlp", debug=False)
    assert any("could not update yt-dlp" in r.message.lower() or "could not update" in r.message.lower() for r in caplog.records)


def test_configure_logging_sets_levels():
    # ensure calling configure_logging flips global root logger level
    # clear existing handlers so basicConfig can take effect in test
    logging.root.handlers.clear()
    cli_mod.configure_logging(True)
    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG
    logging.root.handlers.clear()
    cli_mod.configure_logging(False)
    assert logging.getLogger().getEffectiveLevel() == logging.INFO

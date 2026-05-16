from __future__ import annotations

from src.app.core.download.downloader import Downloader


def test_build_format_defaults_to_best_mp4():
    fmt = Downloader.build_format(None)
    assert "height<=" not in fmt
    assert "best[ext=mp4]" in fmt


def test_build_format_applies_height_cap():
    fmt = Downloader.build_format("720p")
    assert "height<=720" in fmt


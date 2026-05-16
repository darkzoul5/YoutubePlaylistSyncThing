from __future__ import annotations

import os

import pytest

from src.app.core.database.db import Database
from src.app.core.sync.executor import ActionExecutor
from src.app.core.sync.service import SyncService


PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLUmRr21IDW9WCW87FnbWAbIwwZHbf-lAz"


def _require_integration():
    if not os.getenv("INTEGRATION_TEST"):
        pytest.skip("Set INTEGRATION_TEST=1 to enable real download tests")


@pytest.mark.integration
def test_integration_download_video(tmp_path):
    _require_integration()

    db_path = tmp_path / "app.db"
    save_path = tmp_path / "downloads"
    save_path.mkdir(parents=True, exist_ok=True)

    cfg = {
        "url": PLAYLIST_URL,
        "download_mode": "video",
        "save_path": str(save_path),
        "ffmpeg_path": os.getenv("FFMPEG_PATH"),
        "max_download_quality": "1080p",
    }

    db = Database(db_path.resolve())
    service = SyncService(db)
    actions = service.sync_from_config(cfg)

    download_actions = [a for a in actions if a.type.name == "DOWNLOAD"]
    if not download_actions:
        pytest.skip("No download actions produced (playlist empty or already downloaded?)")

    first_vid = download_actions[0].item.video_id if download_actions[0].item else None
    assert first_vid
    subset = [a for a in download_actions if a.item and a.item.video_id == first_vid]
    subset = [a for a in subset if (a.to_name or "").endswith(".mp4")]
    assert subset

    executor = ActionExecutor(db, concurrency=1)
    import asyncio

    asyncio.run(executor.execute(subset, cfg))

    video_dir = save_path / "video"
    assert video_dir.exists()
    assert any(p.suffix.lower() == ".mp4" for p in video_dir.glob("*.mp4"))


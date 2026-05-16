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
def test_integration_download_audio(tmp_path):
    _require_integration()
    if not os.getenv("FFMPEG_PATH"):
        pytest.skip("Set FFMPEG_PATH to a working ffmpeg binary to enable audio extraction downloads")

    db_path = tmp_path / "app.db"
    save_path = tmp_path / "downloads"
    save_path.mkdir(parents=True, exist_ok=True)

    cfg = {
        "url": PLAYLIST_URL,
        "download_mode": "audio",
        "save_path": str(save_path),
        # Must be set to a real ffmpeg path for this test to pass.
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
    # For audio mode there should be a single mp3 target for this video id.
    subset = [a for a in download_actions if a.item and a.item.video_id == first_vid]
    subset = [a for a in subset if (a.to_name or "").endswith(".mp3")]
    assert subset

    executor = ActionExecutor(db, concurrency=1)
    import asyncio

    asyncio.run(executor.execute(subset, cfg))

    audio_dir = save_path / "audio"
    assert audio_dir.exists()
    assert any(p.suffix.lower() == ".mp3" for p in audio_dir.glob("*.mp3"))

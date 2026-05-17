from __future__ import annotations

import asyncio
import sys

from app.core.download.downloader import Downloader
from app.core.download.queue_manager import DownloadJob
from app.core.events.event_bus import EventBus
from app.core.models import PlaylistItem, SyncAction, SyncActionType
from app.core.sync.executor import ActionExecutor


def test_executor_emits_sync_events(tmp_path):
    published: list[tuple[str, dict]] = []

    class TestBus(EventBus):
        async def publish(self, event_name: str, payload: dict) -> None:  # type: ignore[override]
            published.append((event_name, dict(payload)))

    class StubDB:
        def update_local_filename(self, playlist_id: str, video_id: str, filename: str) -> None:
            return None

        def mark_downloaded(self, playlist_id: str, video_id: str, downloaded: bool) -> None:
            return None

    bus = TestBus()
    ex = ActionExecutor(StubDB(), concurrency=1, event_bus=bus)  # type: ignore[arg-type]

    item = PlaylistItem(playlist_id="p", video_id="v", title="t", playlist_index=1)
    actions = [SyncAction(SyncActionType.SKIP, item=item, to_name="0001 - t.mp4")]

    asyncio.run(ex.execute(actions, {"url": "p", "save_path": str(tmp_path)}))

    names = [n for n, _ in published]
    assert "SyncStarted" in names
    assert "SyncSummary" in names
    assert "SyncFinished" in names

    summary = [p for n, p in published if n == "SyncSummary"][0]
    assert summary["playlist_id"] == "p"
    assert "duration_s" in summary
    assert isinstance(summary["counts"], dict)


def test_downloader_progress_hook_calls_callback(tmp_path, monkeypatch):
    callbacks: list[dict] = []

    class DummyYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def download(self, urls):
            hooks = self.opts.get("progress_hooks") or []
            for h in hooks:
                h({"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100, "speed": 1.0, "eta": 1, "filename": "x"})
                h({"status": "finished", "downloaded_bytes": 100, "total_bytes": 100, "speed": 1.0, "eta": 0, "filename": "x"})

    dummy = type("yt_dlp", (), {"YoutubeDL": DummyYDL})
    monkeypatch.setitem(sys.modules, "yt_dlp", dummy)

    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.write_text("x", encoding="utf-8")

    job = DownloadJob(
        item=PlaylistItem(playlist_id="p", video_id="v", title="t", playlist_index=1),
        url="https://example.invalid",
        output_path=tmp_path / "out.mp4",
        ffmpeg_path=str(ffmpeg),
    )
    job.progress_callback = lambda payload: callbacks.append(dict(payload))

    dl = Downloader()
    asyncio.run(dl._download(job))  # type: ignore[attr-defined]

    assert callbacks
    assert any("progress" in c for c in callbacks)

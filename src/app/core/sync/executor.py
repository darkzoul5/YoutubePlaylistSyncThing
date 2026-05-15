from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Iterable, List

from ..download.queue_manager import DownloadJob, QueueManager
from ..download.workers import default_worker
from ..models import SyncAction, SyncActionType
from ..sync.reorder import safe_multi_rename
from ..database.db import Database
from ..utils.yt import extract_playlist_id
from ..events.event_bus import EventBus


class ActionExecutor:
    def __init__(self, db: Database, concurrency: int = 2, event_bus: EventBus | None = None) -> None:
        self.concurrency = max(1, concurrency)
        self.db = db
        self.bus = event_bus

    async def execute(self, actions: Iterable[SyncAction], playlist_cfg: dict) -> None:
        save_path = Path(playlist_cfg.get("save_path", "./downloads")).resolve()
        mode = playlist_cfg.get("download_mode", "audio")

        # Prepare roots
        audio_root = save_path / "audio"
        video_root = save_path / "video"
        audio_root.mkdir(parents=True, exist_ok=True)
        video_root.mkdir(parents=True, exist_ok=True)

        # First, handle renames safely in batch per extension
        await self._apply_renames(actions, audio_root, video_root, playlist_cfg)

        # Then, recycle deletions
        self._apply_deletions(actions, audio_root, video_root, playlist_cfg)

        # Finally, perform downloads concurrently
        await self._apply_downloads(actions, mode, audio_root, video_root, playlist_cfg)

    async def _apply_renames(self, actions: Iterable[SyncAction], audio_root: Path, video_root: Path, playlist_cfg: dict) -> None:
        playlist_id = extract_playlist_id(playlist_cfg.get("url", "")) or playlist_cfg.get("url", "")
        audio_renames = []
        video_renames = []
        applied: List[SyncAction] = []
        for a in actions:
            if a.type != SyncActionType.RENAME or not a.from_name or not a.to_name:
                continue
            if a.to_name.endswith(".mp3"):
                audio_renames.append((audio_root / a.from_name, audio_root / a.to_name))
            elif a.to_name.endswith(".mp4"):
                video_renames.append((video_root / a.from_name, video_root / a.to_name))
            applied.append(a)

        if audio_renames:
            safe_multi_rename(audio_renames)
        if video_renames:
            safe_multi_rename(video_renames)

        # Update DB filenames after successful rename attempts
        for a in applied:
            if a.item and a.to_name:
                try:
                    self.db.update_local_filename(playlist_id, a.item.video_id, a.to_name)
                except Exception:
                    pass
                if self.bus:
                    await self.bus.publish("RenameApplied", {"playlist_id": playlist_id, "video_id": a.item.video_id, "to": a.to_name})

    def _apply_deletions(self, actions: Iterable[SyncAction], audio_root: Path, video_root: Path, playlist_cfg: dict) -> None:
        playlist_id = extract_playlist_id(playlist_cfg.get("url", "")) or playlist_cfg.get("url", "")
        recycle_audio = audio_root.parent / ".recycle" / "audio"
        recycle_video = video_root.parent / ".recycle" / "video"
        recycle_audio.mkdir(parents=True, exist_ok=True)
        recycle_video.mkdir(parents=True, exist_ok=True)

        for a in actions:
            if a.type != SyncActionType.DELETE or not a.from_name:
                continue
            if a.from_name.endswith(".mp3"):
                src = audio_root / a.from_name
                dst = recycle_audio / a.from_name
            else:
                src = video_root / a.from_name
                dst = recycle_video / a.from_name
            if src.exists():
                try:
                    if dst.exists():
                        dst.unlink()
                    shutil.move(str(src), str(dst))
                except Exception:
                    # fallback to delete if move fails
                    try:
                        src.unlink()
                    except Exception:
                        pass
            # Update DB to clear file state
            if a.item:
                try:
                    self.db.clear_file_state(playlist_id, a.item.video_id)
                except Exception:
                    pass
                if self.bus:
                    asyncio.create_task(self.bus.publish("FileRecycled", {"playlist_id": playlist_id, "video_id": a.item.video_id, "name": a.from_name}))

    async def _apply_downloads(self, actions: Iterable[SyncAction], mode: str, audio_root: Path, video_root: Path, playlist_cfg: dict) -> None:
        playlist_id = extract_playlist_id(playlist_cfg.get("url", "")) or playlist_cfg.get("url", "")
        queue = QueueManager(concurrency=self.concurrency)

        async def worker(job: DownloadJob):
            if self.bus and job.item:
                await self.bus.publish("DownloadStarted", {"playlist_id": playlist_id, "video_id": job.item.video_id, "target": str(job.output_path)})
            await default_worker(job)

        await queue.start(worker)
        try:
            jobs: List[DownloadJob] = []
            for a in actions:
                if a.type != SyncActionType.DOWNLOAD or not a.item or not a.to_name:
                    continue
                is_audio = a.to_name.endswith(".mp3")
                root = audio_root if is_audio else video_root
                output_path = root / a.to_name
                output_path.parent.mkdir(parents=True, exist_ok=True)
                url = f"https://www.youtube.com/watch?v={a.item.video_id}"
                job = DownloadJob(item=a.item, output_path=output_path, url=url, mode=("audio" if is_audio else "video"))
                jobs.append(job)
                await queue.enqueue(job)
        finally:
            await queue._queue.join()  # wait for all jobs
            await queue.stop()

        # Persist DB updates for completed jobs
        for job in locals().get("jobs", []):
            if job.item and job.output_path:
                try:
                    if job.state.name == "COMPLETED":
                        self.db.update_local_filename(playlist_id, job.item.video_id, job.output_path.name)
                        self.db.mark_downloaded(playlist_id, job.item.video_id, True)
                        if self.bus:
                            await self.bus.publish("DownloadCompleted", {"playlist_id": playlist_id, "video_id": job.item.video_id, "target": str(job.output_path)})
                    else:
                        # Ensure not marked as downloaded if failed
                        self.db.mark_downloaded(playlist_id, job.item.video_id, False)
                        if self.bus:
                            await self.bus.publish("DownloadFailed", {"playlist_id": playlist_id, "video_id": job.item.video_id, "error": job.error or "unknown"})
                except Exception:
                    pass

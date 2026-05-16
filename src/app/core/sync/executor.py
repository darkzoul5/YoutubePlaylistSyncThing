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
from ..utils.deps import ensure_ffmpeg_available, ensure_yt_dlp_available


class ActionExecutor:
    def __init__(self, db: Database, concurrency: int = 2, event_bus: EventBus | None = None) -> None:
        self.concurrency = max(1, concurrency)
        self.db = db
        self.bus = event_bus

    async def execute(self, actions: Iterable[SyncAction], playlist_cfg: dict) -> None:
        self._preflight_dependencies(actions, playlist_cfg)

        save_path = Path(playlist_cfg.get("save_path", "./downloads")).resolve()
        mode = playlist_cfg.get("download_mode", "video")

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

    def _preflight_dependencies(self, actions: Iterable[SyncAction], playlist_cfg: dict) -> None:
        """
        Fail fast on core runtime dependencies before doing any filesystem work.

        This keeps errors consistent regardless of entrypoint (CLI, bootstrap, tests, etc.).
        """
        needs_download = any(a.type == SyncActionType.DOWNLOAD for a in actions)
        if not needs_download:
            return

        # yt-dlp is required for any download job (Python API usage)
        ensure_yt_dlp_available()

        # ffmpeg is only required when we will extract audio (audio/both modes)
        needs_audio = any((a.to_name or "").lower().endswith(".mp3") for a in actions if a.type == SyncActionType.DOWNLOAD)
        if needs_audio:
            ffmpeg_hint = playlist_cfg.get("ffmpeg_path", "ffmpeg")
            ensure_ffmpeg_available(str(ffmpeg_hint) if ffmpeg_hint is not None else None)

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
        concurrency_cfg = playlist_cfg.get("max_parallel_downloads", self.concurrency)
        try:
            concurrency = int(concurrency_cfg) if concurrency_cfg is not None else self.concurrency
        except Exception:
            concurrency = self.concurrency
        queue = QueueManager(concurrency=concurrency)

        retry_max_cfg = playlist_cfg.get("retry_max_retries", 2)
        retry_delay_cfg = playlist_cfg.get("retry_delay_seconds", 1.5)
        try:
            retry_max_retries = int(retry_max_cfg) if retry_max_cfg is not None else 2
        except Exception:
            retry_max_retries = 2
        try:
            retry_delay_seconds = float(retry_delay_cfg) if retry_delay_cfg is not None else 1.5
        except Exception:
            retry_delay_seconds = 1.5

        async def worker(job: DownloadJob):
            if self.bus and job.item:
                await self.bus.publish("DownloadStarted", {"playlist_id": playlist_id, "video_id": job.item.video_id, "target": str(job.output_path)})
            await default_worker(job, max_retries=retry_max_retries, delay_seconds=retry_delay_seconds)

        await queue.start(worker)
        try:
            jobs: List[DownloadJob] = []

            # Collapse 'both' into single video download + local audio extraction
            # Build per-video desired outputs
            by_vid: dict[str, dict[str, str]] = {}
            for a in actions:
                if a.type != SyncActionType.DOWNLOAD or not a.item or not a.to_name:
                    continue
                d = by_vid.setdefault(a.item.video_id, {})
                if a.to_name.endswith(".mp3"):
                    d["audio"] = a.to_name
                elif a.to_name.endswith(".mp4"):
                    d["video"] = a.to_name

            ffmpeg_cfg = str(playlist_cfg.get("ffmpeg_path", "ffmpeg")) if playlist_cfg.get("ffmpeg_path") is not None else None
            max_quality_cfg = playlist_cfg.get("max_download_quality")
            temp_video_root = video_root / ".tmp"
            temp_video_root.mkdir(parents=True, exist_ok=True)

            for a in actions:
                if a.type != SyncActionType.DOWNLOAD or not a.item or not a.to_name:
                    continue
                vid = a.item.video_id
                targets = by_vid.get(vid, {})

                # If both audio and video requested for this video id, enqueue only video job with audio_output_path
                if targets.get("audio") and targets.get("video"):
                    # only create job once, when encountering the video target
                    if a.to_name.endswith(".mp4"):
                        video_path = video_root / targets["video"]
                        audio_path = audio_root / targets["audio"]
                        for p in (video_path.parent, audio_path.parent):
                            p.mkdir(parents=True, exist_ok=True)
                        url = f"https://www.youtube.com/watch?v={vid}"
                        job = DownloadJob(
                            item=a.item,
                            output_path=video_path,
                            url=url,
                            mode="video",
                            ffmpeg_path=ffmpeg_cfg,
                            max_download_quality=max_quality_cfg,
                            audio_output_path=audio_path,
                        )
                        jobs.append(job)
                        await queue.enqueue(job)
                    # skip creating a separate audio job
                    continue

                # Normal single-output path
                is_audio = a.to_name.endswith(".mp3")
                url = f"https://www.youtube.com/watch?v={vid}"

                if is_audio:
                    # Audio-only: download video to temp, extract mp3, then delete video
                    audio_path = audio_root / a.to_name
                    audio_path.parent.mkdir(parents=True, exist_ok=True)
                    # build temp video filename from audio base
                    temp_base = a.to_name.rsplit(".", 1)[0] + ".mp4"
                    video_temp = temp_video_root / temp_base
                    job = DownloadJob(
                        item=a.item,
                        output_path=video_temp,
                        url=url,
                        mode="video",
                        ffmpeg_path=ffmpeg_cfg,
                        max_download_quality=max_quality_cfg,
                        audio_output_path=audio_path,
                        keep_video=False,
                    )
                    jobs.append(job)
                    await queue.enqueue(job)
                else:
                    # Video-only
                    video_path = video_root / a.to_name
                    video_path.parent.mkdir(parents=True, exist_ok=True)
                    job = DownloadJob(
                        item=a.item,
                        output_path=video_path,
                        url=url,
                        mode="video",
                        ffmpeg_path=ffmpeg_cfg,
                        max_download_quality=max_quality_cfg,
                    )
                    jobs.append(job)
                    await queue.enqueue(job)
        finally:
            await queue.join()  # wait for all jobs
            await queue.stop()

        # Persist DB updates for completed jobs
        for job in locals().get("jobs", []):
            if job.item and job.output_path:
                try:
                    if job.state.name == "COMPLETED":
                        # Prefer audio filename if produced
                        final_name = job.audio_output_path.name if job.audio_output_path is not None else job.output_path.name
                        self.db.update_local_filename(playlist_id, job.item.video_id, final_name)
                        self.db.mark_downloaded(playlist_id, job.item.video_id, True)
                        if self.bus:
                            await self.bus.publish("DownloadCompleted", {"playlist_id": playlist_id, "video_id": job.item.video_id, "target": str(job.audio_output_path or job.output_path)})
                    else:
                        # Ensure not marked as downloaded if failed
                        self.db.mark_downloaded(playlist_id, job.item.video_id, False)
                        if self.bus:
                            await self.bus.publish("DownloadFailed", {"playlist_id": playlist_id, "video_id": job.item.video_id, "error": job.error or "unknown"})
                except Exception:
                    pass

from __future__ import annotations

import asyncio
import logging
from .downloader import Downloader
from .queue_manager import DownloadJob, JobState


async def default_worker(job: DownloadJob, *, max_retries: int = 2, delay_seconds: float = 1.5):
    log = logging.getLogger(__name__)
    dl = Downloader(ffmpeg_path=job.ffmpeg_path)
    attempt = 0
    while attempt <= max_retries:
        await dl.handle_job(job)
        if job.state == JobState.COMPLETED:
            return
        attempt += 1
        if attempt <= max_retries:
            wait = delay_seconds * (2 ** (attempt - 1))
            log.warning(
                "retrying download attempt=%s/%s video_id=%s wait=%.1fs error=%s",
                attempt,
                max_retries,
                getattr(getattr(job, "item", None), "video_id", None),
                wait,
                job.error,
            )
            await asyncio.sleep(wait)

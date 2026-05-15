from __future__ import annotations

import asyncio
from .downloader import Downloader
from .queue_manager import DownloadJob, JobState


async def default_worker(job: DownloadJob, *, max_retries: int = 2, delay_seconds: float = 1.5):
    dl = Downloader()
    attempt = 0
    while attempt <= max_retries:
        await dl.handle_job(job)
        if job.state == JobState.COMPLETED:
            return
        attempt += 1
        if attempt <= max_retries:
            await asyncio.sleep(delay_seconds)

from __future__ import annotations

from .downloader import Downloader
from .queue_manager import DownloadJob


async def default_worker(job: DownloadJob):
    dl = Downloader()
    await dl.handle_job(job)

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from ..models import PlaylistItem


class JobState(str, Enum):
    QUEUED = "Queued"
    DOWNLOADING = "Downloading"
    CONVERTING = "Converting"
    COMPLETED = "Completed"
    FAILED = "Failed"
    SKIPPED = "Skipped"
    CANCELLED = "Cancelled"


@dataclass
class DownloadJob:
    item: PlaylistItem
    output_path: Optional[Path] = None
    url: Optional[str] = None
    mode: str = "audio"  # audio|video
    state: JobState = JobState.QUEUED
    error: Optional[str] = None
    ffmpeg_path: Optional[str] = None
    max_download_quality: Optional[str] = None
    audio_output_path: Optional[Path] = None  # when mode=video and we also want mp3
    keep_video: bool = True


class QueueManager:
    def __init__(self, concurrency: int = 2) -> None:
        self._queue: "asyncio.Queue[DownloadJob]" = asyncio.Queue()
        self._concurrency = max(1, concurrency)
        self._workers: list[asyncio.Task[None]] = []
        self._stopped = asyncio.Event()

    async def start(self, worker_coro):
        async def runner(idx: int):
            while not self._stopped.is_set():
                job = await self._queue.get()
                try:
                    await worker_coro(job)
                finally:
                    self._queue.task_done()

        self._workers = [asyncio.create_task(runner(i)) for i in range(self._concurrency)]

    async def stop(self):
        self._stopped.set()
        for w in self._workers:
            w.cancel()
        self._workers.clear()

    async def enqueue(self, job: DownloadJob):
        await self._queue.put(job)

    async def join(self) -> None:
        await self._queue.join()

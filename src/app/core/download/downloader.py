from __future__ import annotations

from typing import Optional

from .queue_manager import DownloadJob, JobState


class Downloader:
    """
    Thin wrapper around yt-dlp usage. For MVP, this is a placeholder
    where actual download logic will land (audio/video/both).
    """

    def __init__(self, yt_dlp_path: Optional[str] = None, ffmpeg_path: Optional[str] = None) -> None:
        self.yt_dlp_path = yt_dlp_path
        self.ffmpeg_path = ffmpeg_path

    async def handle_job(self, job: DownloadJob):
        try:
            job.state = JobState.DOWNLOADING
            # TODO: Implement actual download via yt-dlp Python API or subprocess
            # For now, mark as completed without side effects.
            job.state = JobState.COMPLETED
        except Exception as exc:  # pragma: no cover - placeholder
            job.state = JobState.FAILED
            job.error = str(exc)

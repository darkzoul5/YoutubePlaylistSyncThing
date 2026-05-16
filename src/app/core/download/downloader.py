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

    @staticmethod
    def build_format(max_download_quality) -> str:
        def parse_height_cap(value) -> int | None:
            if value is None:
                return None
            if isinstance(value, int):
                return value if value > 0 else None
            s = str(value).strip().lower()
            if not s or s in {"best", "max", "auto", "none", "null"}:
                return None
            digits = "".join(ch for ch in s if ch.isdigit())
            if not digits:
                return None
            try:
                cap = int(digits)
            except Exception:
                return None
            return cap if cap > 0 else None

        cap = parse_height_cap(max_download_quality)
        if cap is not None:
            return f"best[ext=mp4][acodec!=none][vcodec!=none][height<={cap}]/best[ext=mp4][height<={cap}]/best[ext=mp4]"
        return "best[ext=mp4][acodec!=none][vcodec!=none]/best[ext=mp4]"

    async def handle_job(self, job: DownloadJob):
        try:
            job.state = JobState.DOWNLOADING
            await self._download(job)
            # Optional local audio extraction when requested
            if job.mode == "video" and job.audio_output_path is not None:
                await self._extract_audio(job)
                # Remove the video if requested (audio-only mode)
                if not job.keep_video and job.output_path:
                    try:
                        job.output_path.unlink(missing_ok=True)
                    except Exception:
                        pass
            job.state = JobState.COMPLETED
        except Exception as exc:  # pragma: no cover - environment dependent
            job.state = JobState.FAILED
            job.error = str(exc)

    async def _download(self, job: DownloadJob):
        # Use yt-dlp Python API, executed in a worker thread
        import asyncio

        def run():
            import yt_dlp  # type: ignore

            class _QuietLogger:
                def debug(self, msg):
                    pass
                def warning(self, msg):
                    pass
                def error(self, msg):
                    # swallow inner repeats; errors are surfaced via exceptions
                    pass
                def info(self, msg):
                    pass

            outtmpl = str(job.output_path)

            fmt = self.build_format(getattr(job, "max_download_quality", None))

            # All modes download a single muxed mp4 when possible.
            # This avoids any ffmpeg-driven merging during the download step, satisfying:
            #   - video: "original file, no processing"
            #   - audio/both: extraction is done separately after download
            ydl_opts = {
                "format": fmt,
                "outtmpl": outtmpl,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "logger": _QuietLogger(),
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[attr-defined]
                ydl.download([job.url])

        await asyncio.to_thread(run)

    async def _extract_audio(self, job: DownloadJob):
        import asyncio
        from shutil import which

        src = job.output_path
        dst = job.audio_output_path
        if not src or not dst:
            return

        def run():
            ffmpeg_exe = job.ffmpeg_path or self.ffmpeg_path or which("ffmpeg") or "ffmpeg"
            import subprocess
            cmd = [
                str(ffmpeg_exe),
                "-y",
                "-i",
                str(src),
                "-vn",
                "-codec:a",
                "libmp3lame",
                "-q:a",
                "0",
                str(dst),
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Mark converting state only for local clarity; not published
        job.state = JobState.CONVERTING
        await asyncio.to_thread(run)

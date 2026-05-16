from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..models import PlaylistItem


class PlaylistScanner:
    """
    Fetches remote playlist entries using yt-dlp (no downloads).

    This class intentionally avoids strict dependencies at import time. If
    yt_dlp is unavailable, call sites should handle the raised ImportError.
    """

    def __init__(self) -> None:
        pass

    def scan(self, playlist_url: str, playlist_id: str, *, ffmpeg_path: Optional[str] = None) -> List[PlaylistItem]:
        try:
            import yt_dlp  # type: ignore
        except Exception as exc:  # pragma: no cover - environment dependent
            raise ImportError("yt_dlp is required to scan playlists") from exc

        ydl_opts = {
            "extract_flat": True,
            "skip_download": True,
            "quiet": True,
            "dump_single_json": True,
        }

        # If a local ffmpeg binary is configured, pass it through so yt-dlp doesn't rely on PATH.
        if ffmpeg_path:
            try:
                p = Path(str(ffmpeg_path))
                if p.exists():
                    ydl_opts["ffmpeg_location"] = str(p)
            except Exception:
                pass

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[attr-defined]
            info = ydl.extract_info(playlist_url, download=False)

        entries = info.get("entries", []) if isinstance(info, dict) else []
        items: List[PlaylistItem] = []
        for idx, v in enumerate(entries, start=1):
            if not v:
                continue
            title = v.get("title") or "[Unknown]"
            if title in ("[Deleted video]", "[Private video]"):
                continue
            vid = v.get("id") or ""
            if not vid:
                continue
            items.append(
                PlaylistItem(
                    playlist_id=playlist_id,
                    video_id=vid,
                    title=title,
                    playlist_index=idx,
                )
            )
        return items

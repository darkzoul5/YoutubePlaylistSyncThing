from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config.settings import Settings
from .core.database.db import Database
from .core.sync.service import SyncService
from .core.sync.executor import ActionExecutor
from .core.events.event_bus import EventBus
import re
from .core.utils.yt import extract_playlist_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="YouTube Playlist Sync — compute/apply actions")
    parser.add_argument("--apply", action="store_true", help="Apply actions (otherwise compute-only)")
    parser.add_argument("--db", type=Path, default=Path("app/data/app.db"), help="Path to SQLite database")
    parser.add_argument("--playlist", type=int, default=None, help="Only run for a specific playlist index (0-based)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed events (rename/recycle/start)")
    args = parser.parse_args(argv)

    settings = Settings()
    db = Database(args.db.resolve())
    service = SyncService(db)
    bus = EventBus()
    executor = ActionExecutor(db, event_bus=bus)

    seen_errors: set[str] = set()

    ansi = re.compile(r"\x1b\[[0-9;]*m")

    async def on_started(payload):
        if args.verbose:
            vid = payload.get("video_id")
            target = payload.get("target")
            print(f"START: {vid} → {target}")

    async def on_completed(payload):
        pid = payload.get("playlist_id")
        vid = payload.get("video_id")
        target = payload.get("target")
        print(f"OK: {vid} → {target}")

    async def on_failed(payload):
        raw = str(payload.get("error", "failed"))
        msg = ansi.sub("", raw)
        # Print only once per unique message
        if msg not in seen_errors:
            seen_errors.add(msg)
            # Friendly hint for missing ffmpeg
            if "ffprobe and ffmpeg not found" in msg.lower():
                print("ERROR: ffmpeg not found. Install ffmpeg or set 'ffmpeg_path' in config.")
            else:
                print(f"ERROR: {msg}")

    # Subscribe to key events
    bus.subscribe("DownloadStarted", on_started)
    bus.subscribe("DownloadCompleted", on_completed)
    bus.subscribe("DownloadFailed", on_failed)
    if args.verbose:
        async def on_rename(payload):
            print(f"RENAME: {payload.get('video_id')} → {payload.get('to')}")
        async def on_recycle(payload):
            print(f"RECYCLE: {payload.get('video_id')} ← {payload.get('name')}")
        bus.subscribe("RenameApplied", on_rename)
        bus.subscribe("FileRecycled", on_recycle)

    playlists = settings.playlists
    if args.playlist is not None:
        playlists = [playlists[args.playlist]] if 0 <= args.playlist < len(playlists) else []

    for pl in playlists:
        url = pl.get("url")
        pid = extract_playlist_id(url) or (url or "")
        try:
            actions = service.sync_from_config(pl)
        except ImportError as e:
            msg = str(e)
            if "yt_dlp" in msg or "yt-dlp" in msg:
                print("yt-dlp Python package is required. Install with: pip install -U yt-dlp")
                return 2
            raise
        counts: dict[str, int] = {}
        for a in actions:
            counts[a.type.name] = counts.get(a.type.name, 0) + 1
        summary = ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
        print(f"Playlist {pid}: {len(actions)} actions → {summary}")
        if args.apply and actions:
            try:
                asyncio.run(executor.execute(actions, pl))
            except DependencyError as e:
                print(f"ERROR: {e}")
                return 2
            db.set_playlist_last_sync(pid)
            print(f"Applied actions for {pid}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

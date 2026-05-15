from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config.settings import Settings
from .core.database.db import Database
from .core.sync.service import SyncService
from .core.sync.executor import ActionExecutor
from .core.events.event_bus import EventBus
from .core.utils.yt import extract_playlist_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="YouTube Playlist Sync — compute/apply actions")
    parser.add_argument("--apply", action="store_true", help="Apply actions (otherwise compute-only)")
    parser.add_argument("--db", type=Path, default=Path("app/data/app.db"), help="Path to SQLite database")
    parser.add_argument("--playlist", type=int, default=None, help="Only run for a specific playlist index (0-based)")
    args = parser.parse_args(argv)

    settings = Settings()
    db = Database(args.db.resolve())
    service = SyncService(db)
    bus = EventBus()
    executor = ActionExecutor(db, event_bus=bus)

    async def log_event(payload):
        # Placeholder subscriber for future GUI/log integration
        print(f"EVENT: {payload}")

    # Subscribe to key events
    bus.subscribe("DownloadStarted", log_event)
    bus.subscribe("DownloadCompleted", log_event)
    bus.subscribe("DownloadFailed", log_event)
    bus.subscribe("RenameApplied", log_event)
    bus.subscribe("FileRecycled", log_event)

    playlists = settings.playlists
    if args.playlist is not None:
        playlists = [playlists[args.playlist]] if 0 <= args.playlist < len(playlists) else []

    for pl in playlists:
        url = pl.get("url")
        pid = extract_playlist_id(url) or (url or "")
        actions = service.sync_from_config(pl)
        counts: dict[str, int] = {}
        for a in actions:
            counts[a.type.name] = counts.get(a.type.name, 0) + 1
        summary = ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
        print(f"Playlist {pid}: {len(actions)} actions → {summary}")
        if args.apply and actions:
            asyncio.run(executor.execute(actions, pl))
            db.set_playlist_last_sync(pid)
            print(f"Applied actions for {pid}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

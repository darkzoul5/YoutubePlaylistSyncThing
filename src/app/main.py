"""
Entry point for the backend (no GUI).

For now, this verifies configuration + database setup and can run a one-off sync.
Future iterations will wire up scheduler and a GUI.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from .config.settings import Settings
from .core.database.db import Database
from .core.sync.service import SyncService
from .core.sync.executor import ActionExecutor
from .core.utils.yt import extract_playlist_id
from .core.utils.deps import DependencyError


def bootstrap(db_path: Path | None = None) -> None:
    settings = Settings()
    db = Database((db_path or Path("db/app.db")).resolve())
    service = SyncService(db)
    executor = ActionExecutor(db)

    # Iterate configured playlists and compute actions (no execution yet)
    for pl in settings.playlists:
        try:
            actions = service.sync_from_config(pl)
            # Apply actions now
            if actions:
                print(f"Applying {len(actions)} actions for: {pl.get('url')}")
                # Summarize before applying
                counts = {}
                for a in actions:
                    counts[a.type] = counts.get(a.type, 0) + 1
                summary = ", ".join(f"{k.name}:{v}" for k, v in counts.items())
                print(f"Plan → {summary}")
                # Execute
                try:
                    asyncio.run(executor.execute(actions, pl))
                except DependencyError as e:
                    print(f"ERROR: {e}")
                    continue
                # Post summary (no DB readback yet)
                pid = extract_playlist_id(pl.get('url', '')) or pl.get('url', '')
                db.set_playlist_last_sync(pid)
                print("Applied actions.")
            else:
                print(f"No actions needed for: {pl.get('url')}")
        except Exception as exc:  # keep bootstrap resilient during early dev
            print(f"Failed to sync playlist {pl.get('url')}: {exc}")


if __name__ == "__main__":
    bootstrap()

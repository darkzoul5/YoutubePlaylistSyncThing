from __future__ import annotations

"""
Entry point for the new backend (no GUI). For now, this only verifies
that configuration and database setup work. Future iterations will wire
up scanner, diff engine, queue, and scheduler.
"""

from pathlib import Path

from .config.settings import Settings
from .core.database.db import Database
from .core.sync.service import SyncService
from .core.sync.executor import ActionExecutor
from .core.models import SyncActionType


def bootstrap(db_path: Path | None = None) -> None:
    settings = Settings()
    db = Database((db_path or Path("app/data/app.db")).resolve())
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
                import asyncio
                asyncio.run(executor.execute(actions, pl))
                # Post summary (no DB readback yet)
                print("Applied actions.")
            else:
                print(f"No actions needed for: {pl.get('url')}")
        except Exception as exc:  # keep bootstrap resilient during early dev
            print(f"Failed to sync playlist {pl.get('url')}: {exc}")


if __name__ == "__main__":
    bootstrap()

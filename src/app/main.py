from __future__ import annotations

"""
Entry point for the new backend (no GUI). For now, this only verifies
that configuration and database setup work. Future iterations will wire
up scanner, diff engine, queue, and scheduler.
"""

from pathlib import Path

from .config.settings import Settings
from .core.database.db import Database


def bootstrap(db_path: Path | None = None) -> None:
    settings = Settings()
    db = Database((db_path or Path("app/data/app.db")).resolve())
    _ = settings, db  # silence linters for now


if __name__ == "__main__":
    bootstrap()

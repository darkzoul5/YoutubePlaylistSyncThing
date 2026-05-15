from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS playlists (
    id TEXT PRIMARY KEY,
    name TEXT,
    url TEXT,
    path TEXT,
    mode TEXT,
    auto_sync INTEGER,
    sync_interval_minutes INTEGER,
    last_sync TEXT
);

CREATE TABLE IF NOT EXISTS playlist_items (
    playlist_id TEXT,
    video_id TEXT,
    title TEXT,
    playlist_index INTEGER,
    local_filename TEXT,
    downloaded INTEGER,
    last_seen TEXT,
    PRIMARY KEY (playlist_id, video_id)
);
"""


class Database:
    def __init__(self, db_path: Path) -> None:
        self.path = db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._conn:
            self._conn.executescript(SCHEMA)

    def upsert_playlist_items(self, rows: Iterable[tuple]):
        sql = (
            "INSERT INTO playlist_items (playlist_id, video_id, title, playlist_index, local_filename, downloaded, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(playlist_id, video_id) DO UPDATE SET "
            "title=excluded.title, playlist_index=excluded.playlist_index, local_filename=excluded.local_filename, "
            "downloaded=excluded.downloaded, last_seen=datetime('now')"
        )
        with self._conn:
            self._conn.executemany(sql, rows)

    def get_items_index(self, playlist_id: str) -> dict[str, sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT * FROM playlist_items WHERE playlist_id = ?",
            (playlist_id,),
        )
        return {row["video_id"]: row for row in cur.fetchall()}

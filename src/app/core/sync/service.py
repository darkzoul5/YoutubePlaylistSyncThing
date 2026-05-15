from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import List

from ..database.db import Database
from ..models import PlaylistItem, SyncAction
from ..scanner.playlist_scanner import PlaylistScanner
from ..sync.diff_engine import DiffEngine
from ..sync.filesystem import list_files
from ..utils.naming import make_filename, sanitize_title
from ..utils.yt import extract_playlist_id


class SyncService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.scanner = PlaylistScanner()
        self.diff = DiffEngine()

    def _mode_to_extensions(self, mode: str) -> list[str]:
        if mode == "audio":
            return [".mp3"]
        if mode == "video":
            return [".mp4"]
        if mode == "both":
            return [".mp3", ".mp4"]
        return [".mp3"]

    def sync_from_config(self, playlist_cfg: dict) -> List[SyncAction]:
        url: str = playlist_cfg.get("url")
        mode: str = playlist_cfg.get("download_mode", "audio")
        save_path = Path(playlist_cfg.get("save_path", "./downloads")).resolve()
        save_path.mkdir(parents=True, exist_ok=True)

        playlist_id = extract_playlist_id(url) or url
        # Ensure playlist row exists/updated
        self.db.upsert_playlist(
            id=playlist_id,
            name=playlist_cfg.get("name"),
            url=url,
            path=str(save_path),
            mode=mode,
            auto_sync=int(bool(playlist_cfg.get("auto_sync", False))),
            sync_interval_minutes=int(playlist_cfg.get("sync_interval_minutes", 0) or 0),
        )
        items = self.scanner.scan(url, playlist_id)

        sanitized: List[PlaylistItem] = []
        for it in items:
            safe_title = sanitize_title(it.title, it.video_id)
            sanitized.append(
                PlaylistItem(
                    playlist_id=it.playlist_id,
                    video_id=it.video_id,
                    title=safe_title,
                    playlist_index=it.playlist_index,
                    local_filename=None,
                    downloaded=False,
                )
            )

        rows = [
            (
                it.playlist_id,
                it.video_id,
                it.title,
                it.playlist_index,
                None,
                0,
            )
            for it in sanitized
        ]
        self.db.upsert_playlist_items(rows)

        db_index_rows = self.db.get_items_index(playlist_id)
        db_index: dict[str, PlaylistItem] = {}
        for vid, row in db_index_rows.items():
            db_index[vid] = PlaylistItem(
                playlist_id=row["playlist_id"],
                video_id=row["video_id"],
                title=row["title"],
                playlist_index=row["playlist_index"],
                local_filename=row["local_filename"],
                downloaded=bool(row["downloaded"]),
            )

        # Augment remote items with DB-known filenames/download flags
        augmented: List[PlaylistItem] = []
        for it in sanitized:
            known = db_index.get(it.video_id)
            if known is None:
                augmented.append(it)
            else:
                augmented.append(
                    PlaylistItem(
                        playlist_id=it.playlist_id,
                        video_id=it.video_id,
                        title=it.title,
                        playlist_index=it.playlist_index,
                        local_filename=known.local_filename,
                        downloaded=known.downloaded,
                    )
                )

        exts = self._mode_to_extensions(mode)
        merged_actions: List[SyncAction] = []

        # Compute per-extension actions against respective roots
        for ext in exts:
            if ext == ".mp3":
                fs = list_files(save_path / "audio", [".mp3"])
            elif ext == ".mp4":
                fs = list_files(save_path / "video", [".mp4"])
            else:
                fs = list_files(save_path, [ext])
            actions = self.diff.compute_actions(augmented, db_index, fs, ext)
            merged_actions.extend(actions)

        return merged_actions
        for ext in exts:
            mode_dir = "audio" if ext == ".mp3" else "video"
            fs_root = (save_path / mode_dir)
            fs_entries = list_files(fs_root, [ext])
            actions = self.diff.compute_actions(sanitized, db_index, fs_entries, ext)
            merged_actions.extend(actions)

        return [
            {
                "type": a.type,
                "video_id": a.item.video_id if a.item else None,
                "from_name": a.from_name,
                "to_name": a.to_name,
            }
            for a in merged_actions
        ]

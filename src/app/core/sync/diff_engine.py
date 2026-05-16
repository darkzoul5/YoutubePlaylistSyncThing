from __future__ import annotations

from typing import Iterable, List, Mapping, Sequence

from ..models import FilesystemEntry, PlaylistItem, SyncAction, SyncActionType


class DiffEngine:
    """
    Compares remote playlist items, database state, and filesystem to
    produce a list of actions. Initial MVP computes DOWNLOAD/RENAME/DELETE
    based on simple filename scheme "0001 - Title.ext".
    """

    def compute_actions(
        self,
        remote: Sequence[PlaylistItem],
        db_index: Mapping[str, PlaylistItem],
        fs_entries: Iterable[FilesystemEntry],
        extension: str,
    ) -> List[SyncAction]:
        actions: List[SyncAction] = []

        desired_names = {
            item.video_id: f"{item.playlist_index:04d} - {item.title}{extension}"
            for item in remote
        }

        fs_by_name = {e.name: e for e in fs_entries}

        for item in remote:
            desired_name = desired_names[item.video_id]
            # If DB knows the current local filename and it already matches and exists -> nothing to do
            if item.local_filename == desired_name and desired_name in fs_by_name:
                continue

            # If DB knows a different current filename and it exists -> plan a rename
            if item.local_filename and item.local_filename in fs_by_name and item.local_filename != desired_name:
                actions.append(
                    SyncAction(
                        SyncActionType.RENAME,
                        item=item,
                        from_name=item.local_filename,
                        to_name=desired_name,
                    )
                )
                continue

            # If the desired file already exists on disk but DB doesn't reflect it -> skip (already correct)
            if desired_name in fs_by_name:
                actions.append(SyncAction(SyncActionType.SKIP, item=item, to_name=desired_name))
                continue

            # Otherwise, we need to download
            actions.append(SyncAction(SyncActionType.DOWNLOAD, item=item, to_name=desired_name))

        known_ids = {i.video_id for i in remote}
        for vid, db_item in db_index.items():
            if vid not in known_ids and db_item.local_filename:
                actions.append(SyncAction(SyncActionType.DELETE, item=db_item, from_name=db_item.local_filename))

        return actions

from __future__ import annotations

from pathlib import Path

from src.app.core.models import PlaylistItem, SyncAction, SyncActionType
from src.app.core.sync.executor import ActionExecutor
from src.app.core.sync.reorder import safe_multi_rename


def test_safe_multi_rename_swaps_files(tmp_path: Path):
    a = tmp_path / "0001 - A.mp4"
    b = tmp_path / "0002 - B.mp4"
    a.write_text("A", encoding="utf-8")
    b.write_text("B", encoding="utf-8")

    safe_multi_rename([(a, b), (b, a)])

    assert (tmp_path / "0001 - A.mp4").read_text(encoding="utf-8") == "B"
    assert (tmp_path / "0002 - B.mp4").read_text(encoding="utf-8") == "A"


def test_executor_deletes_to_recycle(tmp_path: Path):
    class StubDB:
        def clear_file_state(self, playlist_id: str, video_id: str) -> None:
            return None

    executor = ActionExecutor(StubDB())  # type: ignore[arg-type]

    save_root = tmp_path / "downloads"
    audio_root = save_root / "audio"
    video_root = save_root / "video"
    audio_root.mkdir(parents=True, exist_ok=True)
    video_root.mkdir(parents=True, exist_ok=True)

    victim = audio_root / "0001 - X.mp3"
    victim.write_text("x", encoding="utf-8")

    item = PlaylistItem(playlist_id="p", video_id="v", title="t", playlist_index=1, local_filename=victim.name, downloaded=True)
    action = SyncAction(SyncActionType.DELETE, item=item, from_name=victim.name)

    executor._apply_deletions([action], audio_root, video_root, {"url": "p"})  # type: ignore[attr-defined]

    assert not victim.exists()
    recycled = save_root / ".recycle" / "audio" / victim.name
    assert recycled.exists()


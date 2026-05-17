from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

from ..models import FilesystemEntry


def list_files(root: Path, extensions: Sequence[str]) -> List[FilesystemEntry]:
    exts = {e.lower() for e in extensions}
    results: List[FilesystemEntry] = []
    if not root.exists():
        return results
    for p in root.glob("**/*"):
        if p.is_file() and p.suffix.lower() in exts:
            results.append(FilesystemEntry(name=p.name, path=p))
    return results

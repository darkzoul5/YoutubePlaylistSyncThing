from __future__ import annotations

ILLEGAL_CHARS = '<>:"/\\|?*'


def sanitize_title(title: str, fallback: str) -> str:
    table = str.maketrans({c: "-" for c in ILLEGAL_CHARS})
    safe = (title or "").translate(table).strip()
    return safe if safe else fallback


def make_filename(index: int, title: str, ext: str, width: int = 4) -> str:
    return f"{index:0{width}d} - {title}{ext}"

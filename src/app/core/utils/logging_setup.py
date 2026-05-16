from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(*, verbose: bool = False, log_file: Path | None = None) -> None:
    """
    Configure app-wide logging.

    - Console handler always enabled.
    - Rotating file handler enabled when log_file is provided.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Avoid duplicate handlers on repeated calls (tests, re-entrypoints).
    if getattr(configure_logging, "_configured", False):
        return

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(str(log_file), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

    configure_logging._configured = True  # type: ignore[attr-defined]


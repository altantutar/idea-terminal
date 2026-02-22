"""Structured logging setup for Idea Factory."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
) -> None:
    """Configure the ``idea_factory`` logger hierarchy.

    - Always logs to stderr at WARNING+ (so it doesn't clutter Rich output).
    - Optionally logs to a rotating file at the requested *level*.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    root_logger = logging.getLogger("idea_factory")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Stderr handler — only WARNING+ to avoid interfering with Rich output
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(fmt)
    root_logger.addHandler(stderr_handler)

    # File handler — full detail at the configured level
    if log_file:
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            str(log_path),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
        )
        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        file_handler.setFormatter(fmt)
        root_logger.addHandler(file_handler)

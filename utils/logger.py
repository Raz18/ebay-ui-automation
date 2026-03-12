"""Structured logging with console and optional file output."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from config.settings import Settings


_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Track whether the root handler setup has been performed
_initialized: bool = False


def _initialize_root_logger(settings: Settings) -> None:
    """Configure root logger once with console + optional file handler."""
    global _initialized
    if _initialized:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler — always active
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler — only if LOG_FILE is configured
    if settings.LOG_FILE:
        log_path = Path(settings.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger. Initializes root handlers on first call."""
    settings = Settings.from_env()
    _initialize_root_logger(settings)
    return logging.getLogger(name)

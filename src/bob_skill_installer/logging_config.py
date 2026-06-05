"""Enterprise-grade logging built on :mod:`rich`.

A single console is shared across the package so progress output, the install
report, and log records all render through one sink. Call :func:`configure`
once (the CLI does) to set the level and optionally attach a rotating file
handler; library users get a sensible default the first time they call
:func:`get_logger`.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

_LOGGER_NAME = "bob_skill_installer"
_configured = False

#: Shared console — import this rather than constructing new ``Console`` objects
#: so colorized output and captured test output stay consistent.
console = Console(stderr=True)


def configure(
    *,
    level: int | str = logging.INFO,
    log_file: Path | None = None,
    quiet: bool = False,
) -> logging.Logger:
    """Configure the package logger. Idempotent across repeated calls.

    Args:
        level: Log level for the console handler.
        log_file: When given, a rotating file handler (5 files x 1 MiB) is added
            that always records at ``DEBUG`` for post-mortem support tickets.
        quiet: Suppress console log output (errors still propagate); useful when
            JSON/structured report output is the only thing wanted on stdout.

    Returns:
        The configured package logger.
    """
    global _configured

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    if not quiet:
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            markup=True,
        )
        rich_handler.setLevel(level)
        logger.addHandler(rich_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=1_048_576, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
        )
        logger.addHandler(file_handler)

    _configured = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger, configuring defaults on first use."""
    if not _configured:
        configure()
    base = logging.getLogger(_LOGGER_NAME)
    return base.getChild(name) if name else base

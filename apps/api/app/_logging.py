"""Structured JSON logging.

Mirrors the content-generator's `generators/_logging.py` so both sides of the
system log the same JSON shape. Logging always goes to stderr (so uvicorn /
journald / container log drivers capture it); set ``LOG_FILE`` (in .env or the
environment) to also write to a rotating log file.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

from app.config import get_settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        # Attach any extra fields
        for k, v in record.__dict__.items():
            if k in ("args", "asctime", "created", "exc_info", "exc_text",
                     "filename", "funcName", "levelname", "levelno", "lineno",
                     "module", "msecs", "message", "msg", "name", "pathname",
                     "process", "processName", "relativeCreated", "stack_info",
                     "thread", "threadName", "taskName"):
                continue
            payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _build_handlers() -> list[logging.Handler]:
    settings = get_settings()
    formatter = JsonFormatter()
    handlers: list[logging.Handler] = []

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(formatter)
    handlers.append(stream)

    # Optionally also write to a rotating log file. Enabled by setting LOG_FILE;
    # the stderr stream is always kept so journald / container log drivers still
    # capture output.
    if settings.log_file:
        file_handler = RotatingFileHandler(
            settings.log_file,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    return handlers


def _level() -> int:
    return getattr(logging, get_settings().log_level.upper(), logging.INFO)


def configure_logging() -> None:
    """Install JSON (and optional rotating-file) handlers on the root and
    uvicorn loggers. Call once on startup."""
    handlers = _build_handlers()
    level = _level()

    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(level)

    # Route uvicorn's own loggers through the root handlers instead of their
    # default console formatter, so access/error logs share the JSON shape and
    # land in the file too.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv = logging.getLogger(name)
        uv.handlers = []
        uv.propagate = True
        uv.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers and not logging.getLogger().handlers:
        # Standalone use (e.g. a script that didn't call configure_logging).
        logger.handlers = _build_handlers()
        logger.setLevel(_level())
        logger.propagate = False
    return logger

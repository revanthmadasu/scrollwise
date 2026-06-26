"""Structured JSON logging."""

import json
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler


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


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        formatter = JsonFormatter()

        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Optionally also write to a rotating log file. Enabled by setting
        # CONTENT_GEN_LOG_FILE; the stderr stream is always kept so journald /
        # container log drivers still capture output.
        log_file = os.environ.get("CONTENT_GEN_LOG_FILE")
        if log_file:
            max_bytes = int(os.environ.get("CONTENT_GEN_LOG_MAX_BYTES", 10 * 1024 * 1024))
            backup_count = int(os.environ.get("CONTENT_GEN_LOG_BACKUP_COUNT", 5))
            file_handler = RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        level = os.environ.get("CONTENT_GEN_LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, level, logging.INFO))
        logger.propagate = False
    return logger

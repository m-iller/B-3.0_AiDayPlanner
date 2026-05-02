"""
Structured JSON logger factory for AI Day Planner.

Every log entry includes: timestamp (ISO 8601), level, module, message.
No print() statements. Logger is injectable — callers receive a Logger instance.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    """Formats each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        # Attach any extra fields the caller passed via `extra=`
        for key, value in record.__dict__.items():
            if key not in _STDLIB_LOG_RECORD_ATTRS and not key.startswith("_"):
                entry[key] = value
        return json.dumps(entry, default=str)


# Fields that belong to the stdlib LogRecord — excluded from extra passthrough
_STDLIB_LOG_RECORD_ATTRS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "taskName",
    }
)


def configure_logging(level: str) -> None:
    """
    Configure the root logger with a JSON formatter at the given level.

    Args:
        level: One of DEBUG, INFO, WARNING, ERROR (case-insensitive).
    """
    numeric_level = logging.getLevelName(level.upper())
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level!r}")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.setLevel(numeric_level)
    # Replace existing handlers to avoid duplicate output
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(module: str, level: str = "INFO") -> logging.Logger:
    """
    Return a named Logger configured with a JSON formatter.

    The returned logger is independent — callers inject it rather than
    relying on a global singleton.

    Args:
        module: Logical module name embedded in every log entry.
        level:  Log level string (DEBUG | INFO | WARNING | ERROR).

    Returns:
        A stdlib Logger instance with a JSON stream handler attached.
    """
    numeric_level = logging.getLevelName(level.upper())
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level!r}")

    logger = logging.getLogger(module)
    logger.setLevel(numeric_level)

    # Attach a JSON handler only if none exists yet for this logger
    if not any(isinstance(h, logging.StreamHandler) and isinstance(h.formatter, _JsonFormatter)
               for h in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)

    # Prevent propagation to root to avoid duplicate output
    logger.propagate = False

    return logger

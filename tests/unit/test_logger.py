"""
Unit tests for ai_day_planner/logger.py

Covers:
- Output is valid JSON per line
- Every entry has timestamp, level, module, message fields
- Log level is configurable
- No print() statements in production logger module (structural check)
"""

from __future__ import annotations

import ast
import importlib
import inspect
import io
import json
import logging
import sys
from pathlib import Path

import pytest

from ai_day_planner.logger import configure_logging, get_logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture_log(logger: logging.Logger, level: int, message: str) -> dict:
    """Emit one log record and return the parsed JSON dict."""
    buf = io.StringIO()
    # Temporarily redirect all handlers on this logger to our buffer
    original_handlers = logger.handlers[:]
    for h in original_handlers:
        logger.removeHandler(h)

    handler = logging.StreamHandler(buf)
    from ai_day_planner.logger import _JsonFormatter
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)

    try:
        logger.log(level, message)
    finally:
        logger.removeHandler(handler)
        for h in original_handlers:
            logger.addHandler(h)

    output = buf.getvalue().strip()
    assert output, "Logger produced no output"
    return json.loads(output)


# ---------------------------------------------------------------------------
# Tests: JSON output
# ---------------------------------------------------------------------------

class TestJsonOutput:
    def test_output_is_valid_json(self):
        logger = get_logger("test.json_output")
        entry = _capture_log(logger, logging.INFO, "hello world")
        assert isinstance(entry, dict)

    def test_single_line_per_record(self):
        """Each log record must produce exactly one line of JSON."""
        buf = io.StringIO()
        from ai_day_planner.logger import _JsonFormatter
        handler = logging.StreamHandler(buf)
        handler.setFormatter(_JsonFormatter())

        logger = logging.getLogger("test.single_line")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.propagate = False

        logger.info("line one")
        logger.info("line two")

        lines = [l for l in buf.getvalue().splitlines() if l.strip()]
        assert len(lines) == 2
        for line in lines:
            json.loads(line)  # must not raise


# ---------------------------------------------------------------------------
# Tests: Required fields
# ---------------------------------------------------------------------------

class TestRequiredFields:
    def test_has_timestamp(self):
        logger = get_logger("test.fields")
        entry = _capture_log(logger, logging.INFO, "msg")
        assert "timestamp" in entry

    def test_timestamp_is_iso8601(self):
        from datetime import datetime
        logger = get_logger("test.timestamp")
        entry = _capture_log(logger, logging.INFO, "msg")
        # Should parse without error
        datetime.fromisoformat(entry["timestamp"])

    def test_has_level(self):
        logger = get_logger("test.level_field")
        entry = _capture_log(logger, logging.WARNING, "msg")
        assert "level" in entry
        assert entry["level"] == "WARNING"

    def test_has_module(self):
        logger = get_logger("my.module.name")
        entry = _capture_log(logger, logging.INFO, "msg")
        assert "module" in entry
        assert entry["module"] == "my.module.name"

    def test_has_message(self):
        logger = get_logger("test.message_field")
        entry = _capture_log(logger, logging.INFO, "the message text")
        assert "message" in entry
        assert entry["message"] == "the message text"

    def test_all_four_required_fields_present(self):
        logger = get_logger("test.all_fields")
        entry = _capture_log(logger, logging.INFO, "check all")
        for field in ("timestamp", "level", "module", "message"):
            assert field in entry, f"Missing required field: {field}"


# ---------------------------------------------------------------------------
# Tests: Configurable level
# ---------------------------------------------------------------------------

class TestConfigurableLevel:
    def test_debug_level_emits_debug(self):
        logger = get_logger("test.debug_level", level="DEBUG")
        entry = _capture_log(logger, logging.DEBUG, "debug msg")
        assert entry["level"] == "DEBUG"

    def test_warning_level_suppresses_info(self):
        """Logger at WARNING should not emit INFO records."""
        buf = io.StringIO()
        from ai_day_planner.logger import _JsonFormatter
        handler = logging.StreamHandler(buf)
        handler.setFormatter(_JsonFormatter())

        logger = logging.getLogger("test.suppress_info")
        logger.setLevel(logging.WARNING)
        logger.addHandler(handler)
        logger.propagate = False

        logger.info("should be suppressed")
        assert buf.getvalue().strip() == ""

    def test_error_level_string(self):
        logger = get_logger("test.error_level", level="ERROR")
        entry = _capture_log(logger, logging.ERROR, "error msg")
        assert entry["level"] == "ERROR"

    def test_invalid_level_raises(self):
        with pytest.raises(ValueError):
            get_logger("test.bad_level", level="NONSENSE")

    def test_configure_logging_sets_root_level(self):
        configure_logging("DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        # Restore
        configure_logging("INFO")

    def test_configure_logging_invalid_level_raises(self):
        with pytest.raises(ValueError):
            configure_logging("INVALID")


# ---------------------------------------------------------------------------
# Tests: No print() in production code (structural check)
# ---------------------------------------------------------------------------

class TestNoPrintStatements:
    def test_logger_module_has_no_print_calls(self):
        """Parse logger.py AST and assert no Call nodes invoke 'print'."""
        source_path = Path(__file__).parent.parent.parent / "ai_day_planner" / "logger.py"
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        print_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ]
        assert print_calls == [], (
            f"Found {len(print_calls)} print() call(s) in logger.py — "
            "production code must not use print()"
        )

    def test_database_module_has_no_print_calls(self):
        """Same structural check for database.py."""
        source_path = Path(__file__).parent.parent.parent / "ai_day_planner" / "database.py"
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        print_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ]
        assert print_calls == [], (
            f"Found {len(print_calls)} print() call(s) in database.py"
        )

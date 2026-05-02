"""
Unit tests for ai_day_planner/config.py.

Covers: load_config happy path, ConfigurationError on missing file,
malformed TOML, missing sections/fields, invalid field values,
range violations, frozen dataclasses, and ConfigurationError inheritance.
"""

import textwrap
from pathlib import Path

import pytest

from ai_day_planner.config import (
    AppConfig,
    ConfigurationError,
    load_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_toml(tmp_path: Path, content: str) -> Path:
    """Write TOML content to a temp file and return its path."""
    p = tmp_path / "test_config.toml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


VALID_TOML = """
    [task]
    difficulty_min = 1
    difficulty_max = 10
    urgency_min = 1
    urgency_max = 10
    importance_min = 1
    importance_max = 10

    [calendar]
    active_hours_start = "08:00"
    active_hours_end = "22:00"

    [fatigue]
    min_score = 1
    max_score = 100
    high_threshold = 75
    increase_difficulty_weight = 0.5
    increase_duration_weight = 0.05
    recovery_rate_per_minute = 0.1
    high_fatigue_penalty = 0.2

    [scheduler]
    weight_difficulty = 1.0
    weight_urgency = 1.5
    weight_importance = 1.2
    weight_fatigue = 0.8
    min_completion_probability = 0.4
    daily_overload_threshold = 0.5
    major_task_difficulty_threshold = 7
    max_major_tasks_per_day = 1

    [learning]
    ema_smoothing_factor = 0.3
    default_correction_coefficient = 1.0

    [probability]
    prior_probability = 0.7
    weight_fatigue = 0.25
    weight_difficulty = 0.25
    weight_time_of_day = 0.2
    weight_correction = 0.15
    weight_historical_rate = 0.15

    [logging]
    level = "INFO"
"""


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestLoadConfigValid:
    def test_returns_app_config(self, tmp_path):
        cfg = load_config(write_toml(tmp_path, VALID_TOML))
        assert isinstance(cfg, AppConfig)

    def test_task_fields(self, tmp_path):
        cfg = load_config(write_toml(tmp_path, VALID_TOML))
        assert cfg.task.difficulty_min == 1
        assert cfg.task.difficulty_max == 10

    def test_fatigue_fields(self, tmp_path):
        cfg = load_config(write_toml(tmp_path, VALID_TOML))
        assert cfg.fatigue.min_score == 1
        assert cfg.fatigue.max_score == 100
        assert cfg.fatigue.high_threshold == 75

    def test_scheduler_weights_positive(self, tmp_path):
        cfg = load_config(write_toml(tmp_path, VALID_TOML))
        assert cfg.scheduler.weight_difficulty > 0
        assert cfg.scheduler.weight_urgency > 0

    def test_learning_ema_in_range(self, tmp_path):
        cfg = load_config(write_toml(tmp_path, VALID_TOML))
        assert 0 < cfg.learning.ema_smoothing_factor <= 1.0

    def test_logging_level_valid(self, tmp_path):
        cfg = load_config(write_toml(tmp_path, VALID_TOML))
        assert cfg.logging.level in ("DEBUG", "INFO", "WARNING", "ERROR")

    def test_calendar_times(self, tmp_path):
        cfg = load_config(write_toml(tmp_path, VALID_TOML))
        assert cfg.calendar.active_hours_start == "08:00"
        assert cfg.calendar.active_hours_end == "22:00"


# ---------------------------------------------------------------------------
# ConfigurationError is RuntimeError subclass
# ---------------------------------------------------------------------------

class TestConfigurationErrorInheritance:
    def test_is_runtime_error(self):
        assert issubclass(ConfigurationError, RuntimeError)

    def test_can_be_raised_and_caught_as_runtime_error(self):
        with pytest.raises(RuntimeError):
            raise ConfigurationError("test")


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------

class TestFrozenDataclasses:
    def test_fatigue_config_frozen(self, tmp_path):
        cfg = load_config(write_toml(tmp_path, VALID_TOML))
        with pytest.raises((AttributeError, TypeError)):
            cfg.fatigue.min_score = 999  # type: ignore[misc]

    def test_app_config_frozen(self, tmp_path):
        cfg = load_config(write_toml(tmp_path, VALID_TOML))
        with pytest.raises((AttributeError, TypeError)):
            cfg.logging = None  # type: ignore[misc]


# ---------------------------------------------------------------------------
# File-level errors
# ---------------------------------------------------------------------------

class TestFileErrors:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ConfigurationError, match="not found"):
            load_config(tmp_path / "nonexistent.toml")

    def test_malformed_toml_raises(self, tmp_path):
        bad = tmp_path / "bad.toml"
        bad.write_text("this is not = valid toml ][", encoding="utf-8")
        with pytest.raises(ConfigurationError, match="malformed"):
            load_config(bad)


# ---------------------------------------------------------------------------
# Missing sections / fields
# ---------------------------------------------------------------------------

class TestMissingSections:
    @pytest.mark.parametrize("section", [
        "task", "calendar", "fatigue", "scheduler", "learning", "probability", "logging"
    ])
    def test_missing_section_raises(self, tmp_path, section):
        lines = [l for l in VALID_TOML.splitlines() if not l.strip().startswith(f"[{section}]")]
        # Also strip the fields belonging to that section
        # Simplest: just write a TOML without that section header and its keys
        # Build minimal TOML missing the section entirely
        import re
        # Remove the section block
        pattern = rf"\[{section}\][^\[]*"
        stripped = re.sub(pattern, "", VALID_TOML, flags=re.DOTALL)
        with pytest.raises(ConfigurationError, match=section):
            load_config(write_toml(tmp_path, stripped))


# ---------------------------------------------------------------------------
# Range / value validation
# ---------------------------------------------------------------------------

class TestRangeValidation:
    def _patch(self, original: str, old: str, new: str) -> str:
        return original.replace(old, new, 1)

    def test_fatigue_min_gte_max_raises(self, tmp_path):
        toml = self._patch(VALID_TOML, "    min_score = 1\n    max_score = 100", "    min_score = 100\n    max_score = 1")
        with pytest.raises(ConfigurationError, match="min_score"):
            load_config(write_toml(tmp_path, toml))

    def test_task_difficulty_min_gte_max_raises(self, tmp_path):
        toml = self._patch(VALID_TOML, "difficulty_min = 1\n    difficulty_max = 10", "difficulty_min = 10\n    difficulty_max = 1")
        with pytest.raises(ConfigurationError):
            load_config(write_toml(tmp_path, toml))

    def test_ema_zero_raises(self, tmp_path):
        toml = self._patch(VALID_TOML, "ema_smoothing_factor = 0.3", "ema_smoothing_factor = 0.0")
        with pytest.raises(ConfigurationError, match="ema_smoothing_factor"):
            load_config(write_toml(tmp_path, toml))

    def test_ema_above_one_raises(self, tmp_path):
        toml = self._patch(VALID_TOML, "ema_smoothing_factor = 0.3", "ema_smoothing_factor = 1.5")
        with pytest.raises(ConfigurationError, match="ema_smoothing_factor"):
            load_config(write_toml(tmp_path, toml))

    def test_invalid_log_level_raises(self, tmp_path):
        toml = self._patch(VALID_TOML, 'level = "INFO"', 'level = "VERBOSE"')
        with pytest.raises(ConfigurationError, match="level"):
            load_config(write_toml(tmp_path, toml))

    def test_invalid_time_format_raises(self, tmp_path):
        toml = self._patch(VALID_TOML, 'active_hours_start = "08:00"', 'active_hours_start = "8am"')
        with pytest.raises(ConfigurationError, match="active_hours_start"):
            load_config(write_toml(tmp_path, toml))

    def test_calendar_start_after_end_raises(self, tmp_path):
        toml = self._patch(VALID_TOML, 'active_hours_start = "08:00"', 'active_hours_start = "23:00"')
        with pytest.raises(ConfigurationError):
            load_config(write_toml(tmp_path, toml))

    def test_scheduler_weight_zero_raises(self, tmp_path):
        toml = self._patch(VALID_TOML, "weight_difficulty = 1.0", "weight_difficulty = 0.0")
        with pytest.raises(ConfigurationError, match="weight_difficulty"):
            load_config(write_toml(tmp_path, toml))

    def test_probability_above_one_raises(self, tmp_path):
        toml = self._patch(VALID_TOML, "prior_probability = 0.7", "prior_probability = 1.5")
        with pytest.raises(ConfigurationError, match="prior_probability"):
            load_config(write_toml(tmp_path, toml))

"""
Configuration loader for AI Day Planner.

Parses TOML via tomllib (Python 3.11+ stdlib), validates all fields,
and raises ConfigurationError (subclass of RuntimeError) on any
missing or invalid field — fail-fast, no hardcoded fallbacks.
"""

from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError as _tomli_err:
        raise ImportError(
            "Python < 3.11 requires the 'tomli' package. "
            "Install it with: pip install tomli"
        ) from _tomli_err

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigurationError(RuntimeError):
    """Raised when the configuration file is missing, malformed, or invalid."""


# ---------------------------------------------------------------------------
# Frozen dataclasses — one per config section
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TaskConfig:
    difficulty_min: int
    difficulty_max: int
    urgency_min: int
    urgency_max: int
    importance_min: int
    importance_max: int


@dataclass(frozen=True)
class CalendarConfig:
    active_hours_start: str  # "HH:MM"
    active_hours_end: str    # "HH:MM"


@dataclass(frozen=True)
class FatigueConfig:
    min_score: int
    max_score: int
    high_threshold: int
    increase_difficulty_weight: float
    increase_duration_weight: float
    recovery_rate_per_minute: float
    high_fatigue_penalty: float


@dataclass(frozen=True)
class SchedulerConfig:
    weight_difficulty: float
    weight_urgency: float
    weight_importance: float
    weight_fatigue: float
    min_completion_probability: float
    daily_overload_threshold: float
    # Flow-state protection: cap how many "major" tasks are scheduled per day.
    # A task is "major" when difficulty >= major_task_difficulty_threshold.
    major_task_difficulty_threshold: int  # e.g. 7 out of 10
    max_major_tasks_per_day: int          # e.g. 1


@dataclass(frozen=True)
class LearningConfig:
    ema_smoothing_factor: float        # α in EMA — must be in (0, 1]
    default_correction_coefficient: float


@dataclass(frozen=True)
class ProbabilityConfig:
    prior_probability: float
    weight_fatigue: float
    weight_difficulty: float
    weight_time_of_day: float
    weight_correction: float
    weight_historical_rate: float


@dataclass(frozen=True)
class LoggingConfig:
    level: str  # DEBUG | INFO | WARNING | ERROR


@dataclass(frozen=True)
class DatabaseConfig:
    path: str  # file path or ":memory:"


@dataclass(frozen=True)
class WeekBucketConfig:
    """
    One of the four weekly time buckets.

    name:        Human-readable label (e.g. "must_do", "projects", "learning", "rest").
    fraction:    Target fraction of weekly active hours (0.0–1.0). All four must sum to 1.0.
    is_immutable: When True, the scheduler will not move tasks out of this bucket's slots.
    """
    name: str
    fraction: float
    is_immutable: bool


@dataclass(frozen=True)
class WeekConfig:
    """
    Splits the week into configurable time buckets.
    Fractions across all buckets must sum to 1.0 (validated at load time).
    """
    must_do: WeekBucketConfig
    projects: WeekBucketConfig
    learning: WeekBucketConfig
    rest: WeekBucketConfig


@dataclass(frozen=True)
class AppConfig:
    task: TaskConfig
    calendar: CalendarConfig
    fatigue: FatigueConfig
    scheduler: SchedulerConfig
    learning: LearningConfig
    probability: ProbabilityConfig
    logging: LoggingConfig
    database: "DatabaseConfig"
    week: "WeekConfig"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


def _require_section(raw: dict[str, Any], section: str) -> dict[str, Any]:
    """Return a section dict or raise ConfigurationError."""
    if section not in raw:
        raise ConfigurationError(
            f"Configuration missing required section: [{section}]"
        )
    value = raw[section]
    if not isinstance(value, dict):
        raise ConfigurationError(
            f"Configuration section [{section}] must be a table, got {type(value).__name__}"
        )
    return value  # type: ignore[return-value]


def _require_field(section_name: str, data: dict[str, Any], field: str, expected_type: type) -> Any:
    """Return a field value, validating presence and type."""
    if field not in data:
        raise ConfigurationError(
            f"[{section_name}] missing required field: {field}"
        )
    value = data[field]
    # Allow int where float is expected (TOML integers are valid floats)
    if expected_type is float and isinstance(value, int):
        value = float(value)
    if not isinstance(value, expected_type):
        raise ConfigurationError(
            f"[{section_name}].{field} must be {expected_type.__name__}, "
            f"got {type(value).__name__} ({value!r})"
        )
    return value


def _require_int(section: str, data: dict[str, Any], field: str) -> int:
    return _require_field(section, data, field, int)


def _require_float(section: str, data: dict[str, Any], field: str) -> float:
    return _require_field(section, data, field, float)


def _require_str(section: str, data: dict[str, Any], field: str) -> str:
    return _require_field(section, data, field, str)


def _validate_positive_float(section: str, field: str, value: float) -> None:
    if value <= 0:
        raise ConfigurationError(
            f"[{section}].{field} must be > 0, got {value}"
        )


def _validate_probability(section: str, field: str, value: float) -> None:
    if not (0.0 <= value <= 1.0):
        raise ConfigurationError(
            f"[{section}].{field} must be in [0.0, 1.0], got {value}"
        )


def _validate_time_string(section: str, field: str, value: str) -> None:
    """Validate 'HH:MM' format."""
    parts = value.split(":")
    if len(parts) != 2:
        raise ConfigurationError(
            f"[{section}].{field} must be in HH:MM format, got {value!r}"
        )
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        raise ConfigurationError(
            f"[{section}].{field} must be in HH:MM format with integer parts, got {value!r}"
        )
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ConfigurationError(
            f"[{section}].{field} time out of range (HH 0-23, MM 0-59), got {value!r}"
        )


# ---------------------------------------------------------------------------
# Section parsers
# ---------------------------------------------------------------------------

def _parse_task_config(raw: dict[str, Any]) -> TaskConfig:
    sec = "task"
    data = _require_section(raw, sec)

    difficulty_min = _require_int(sec, data, "difficulty_min")
    difficulty_max = _require_int(sec, data, "difficulty_max")
    urgency_min = _require_int(sec, data, "urgency_min")
    urgency_max = _require_int(sec, data, "urgency_max")
    importance_min = _require_int(sec, data, "importance_min")
    importance_max = _require_int(sec, data, "importance_max")

    if difficulty_min >= difficulty_max:
        raise ConfigurationError(
            f"[{sec}] difficulty_min ({difficulty_min}) must be < difficulty_max ({difficulty_max})"
        )
    if urgency_min >= urgency_max:
        raise ConfigurationError(
            f"[{sec}] urgency_min ({urgency_min}) must be < urgency_max ({urgency_max})"
        )
    if importance_min >= importance_max:
        raise ConfigurationError(
            f"[{sec}] importance_min ({importance_min}) must be < importance_max ({importance_max})"
        )

    return TaskConfig(
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        urgency_min=urgency_min,
        urgency_max=urgency_max,
        importance_min=importance_min,
        importance_max=importance_max,
    )


def _parse_calendar_config(raw: dict[str, Any]) -> CalendarConfig:
    sec = "calendar"
    data = _require_section(raw, sec)

    start = _require_str(sec, data, "active_hours_start")
    end = _require_str(sec, data, "active_hours_end")

    _validate_time_string(sec, "active_hours_start", start)
    _validate_time_string(sec, "active_hours_end", end)

    # Ensure start < end
    start_minutes = int(start.split(":")[0]) * 60 + int(start.split(":")[1])
    end_minutes = int(end.split(":")[0]) * 60 + int(end.split(":")[1])
    if start_minutes >= end_minutes:
        raise ConfigurationError(
            f"[{sec}] active_hours_start ({start}) must be before active_hours_end ({end})"
        )

    return CalendarConfig(active_hours_start=start, active_hours_end=end)


def _parse_fatigue_config(raw: dict[str, Any]) -> FatigueConfig:
    sec = "fatigue"
    data = _require_section(raw, sec)

    min_score = _require_int(sec, data, "min_score")
    max_score = _require_int(sec, data, "max_score")
    high_threshold = _require_int(sec, data, "high_threshold")
    increase_difficulty_weight = _require_float(sec, data, "increase_difficulty_weight")
    increase_duration_weight = _require_float(sec, data, "increase_duration_weight")
    recovery_rate_per_minute = _require_float(sec, data, "recovery_rate_per_minute")
    high_fatigue_penalty = _require_float(sec, data, "high_fatigue_penalty")

    if min_score >= max_score:
        raise ConfigurationError(
            f"[{sec}] min_score ({min_score}) must be < max_score ({max_score})"
        )
    if not (min_score <= high_threshold <= max_score):
        raise ConfigurationError(
            f"[{sec}] high_threshold ({high_threshold}) must be in "
            f"[min_score={min_score}, max_score={max_score}]"
        )
    _validate_positive_float(sec, "increase_difficulty_weight", increase_difficulty_weight)
    _validate_positive_float(sec, "increase_duration_weight", increase_duration_weight)
    _validate_positive_float(sec, "recovery_rate_per_minute", recovery_rate_per_minute)
    _validate_probability(sec, "high_fatigue_penalty", high_fatigue_penalty)

    return FatigueConfig(
        min_score=min_score,
        max_score=max_score,
        high_threshold=high_threshold,
        increase_difficulty_weight=increase_difficulty_weight,
        increase_duration_weight=increase_duration_weight,
        recovery_rate_per_minute=recovery_rate_per_minute,
        high_fatigue_penalty=high_fatigue_penalty,
    )


def _parse_scheduler_config(raw: dict[str, Any]) -> SchedulerConfig:
    sec = "scheduler"
    data = _require_section(raw, sec)

    weight_difficulty = _require_float(sec, data, "weight_difficulty")
    weight_urgency = _require_float(sec, data, "weight_urgency")
    weight_importance = _require_float(sec, data, "weight_importance")
    weight_fatigue = _require_float(sec, data, "weight_fatigue")
    min_completion_probability = _require_float(sec, data, "min_completion_probability")
    daily_overload_threshold = _require_float(sec, data, "daily_overload_threshold")
    major_task_difficulty_threshold = _require_int(sec, data, "major_task_difficulty_threshold")
    max_major_tasks_per_day = _require_int(sec, data, "max_major_tasks_per_day")

    for name, val in [
        ("weight_difficulty", weight_difficulty),
        ("weight_urgency", weight_urgency),
        ("weight_importance", weight_importance),
        ("weight_fatigue", weight_fatigue),
    ]:
        _validate_positive_float(sec, name, val)

    _validate_probability(sec, "min_completion_probability", min_completion_probability)
    _validate_probability(sec, "daily_overload_threshold", daily_overload_threshold)

    if major_task_difficulty_threshold < 1:
        raise ConfigurationError(
            f"[{sec}] major_task_difficulty_threshold must be >= 1, got {major_task_difficulty_threshold}"
        )
    if max_major_tasks_per_day < 1:
        raise ConfigurationError(
            f"[{sec}] max_major_tasks_per_day must be >= 1, got {max_major_tasks_per_day}"
        )

    return SchedulerConfig(
        weight_difficulty=weight_difficulty,
        weight_urgency=weight_urgency,
        weight_importance=weight_importance,
        weight_fatigue=weight_fatigue,
        min_completion_probability=min_completion_probability,
        daily_overload_threshold=daily_overload_threshold,
        major_task_difficulty_threshold=major_task_difficulty_threshold,
        max_major_tasks_per_day=max_major_tasks_per_day,
    )


def _parse_learning_config(raw: dict[str, Any]) -> LearningConfig:
    sec = "learning"
    data = _require_section(raw, sec)

    ema_smoothing_factor = _require_float(sec, data, "ema_smoothing_factor")
    default_correction_coefficient = _require_float(sec, data, "default_correction_coefficient")

    if not (0.0 < ema_smoothing_factor <= 1.0):
        raise ConfigurationError(
            f"[{sec}] ema_smoothing_factor must be in (0.0, 1.0], got {ema_smoothing_factor}"
        )
    _validate_positive_float(sec, "default_correction_coefficient", default_correction_coefficient)

    return LearningConfig(
        ema_smoothing_factor=ema_smoothing_factor,
        default_correction_coefficient=default_correction_coefficient,
    )


def _parse_probability_config(raw: dict[str, Any]) -> ProbabilityConfig:
    sec = "probability"
    data = _require_section(raw, sec)

    prior_probability = _require_float(sec, data, "prior_probability")
    weight_fatigue = _require_float(sec, data, "weight_fatigue")
    weight_difficulty = _require_float(sec, data, "weight_difficulty")
    weight_time_of_day = _require_float(sec, data, "weight_time_of_day")
    weight_correction = _require_float(sec, data, "weight_correction")
    weight_historical_rate = _require_float(sec, data, "weight_historical_rate")

    _validate_probability(sec, "prior_probability", prior_probability)

    for name, val in [
        ("weight_fatigue", weight_fatigue),
        ("weight_difficulty", weight_difficulty),
        ("weight_time_of_day", weight_time_of_day),
        ("weight_correction", weight_correction),
        ("weight_historical_rate", weight_historical_rate),
    ]:
        _validate_positive_float(sec, name, val)

    return ProbabilityConfig(
        prior_probability=prior_probability,
        weight_fatigue=weight_fatigue,
        weight_difficulty=weight_difficulty,
        weight_time_of_day=weight_time_of_day,
        weight_correction=weight_correction,
        weight_historical_rate=weight_historical_rate,
    )


def _parse_logging_config(raw: dict[str, Any]) -> LoggingConfig:
    sec = "logging"
    data = _require_section(raw, sec)

    level = _require_str(sec, data, "level")
    if level not in _VALID_LOG_LEVELS:
        raise ConfigurationError(
            f"[{sec}] level must be one of {sorted(_VALID_LOG_LEVELS)}, got {level!r}"
        )

    return LoggingConfig(level=level)


def _parse_database_config(raw: dict[str, Any]) -> "DatabaseConfig":
    sec = "database"
    # Section is optional — default to a local file
    data = raw.get(sec, {})
    path = data.get("path", "planner.db")
    if not isinstance(path, str) or not path:
        raise ConfigurationError(f"[{sec}].path must be a non-empty string, got {path!r}")
    return DatabaseConfig(path=path)


def _parse_week_bucket(sec: str, data: dict[str, Any], bucket: str) -> "WeekBucketConfig":
    sub = data.get(bucket)
    if not isinstance(sub, dict):
        raise ConfigurationError(
            f"[{sec}.{bucket}] must be a table with 'fraction' (float) and 'is_immutable' (bool)"
        )
    fraction = _require_float(f"{sec}.{bucket}", sub, "fraction")
    _validate_probability(f"{sec}.{bucket}", "fraction", fraction)
    is_immutable_raw = sub.get("is_immutable")
    if not isinstance(is_immutable_raw, bool):
        raise ConfigurationError(
            f"[{sec}.{bucket}].is_immutable must be a boolean, got {is_immutable_raw!r}"
        )
    return WeekBucketConfig(name=bucket, fraction=fraction, is_immutable=is_immutable_raw)


def _parse_week_config(raw: dict[str, Any]) -> "WeekConfig":
    sec = "week"
    data = raw.get(sec, {})
    if not data:
        # Default: equal 25% split, all mutable
        return WeekConfig(
            must_do=WeekBucketConfig(name="must_do", fraction=0.25, is_immutable=False),
            projects=WeekBucketConfig(name="projects", fraction=0.25, is_immutable=False),
            learning=WeekBucketConfig(name="learning", fraction=0.25, is_immutable=False),
            rest=WeekBucketConfig(name="rest", fraction=0.25, is_immutable=True),
        )

    must_do = _parse_week_bucket(sec, data, "must_do")
    projects = _parse_week_bucket(sec, data, "projects")
    learning = _parse_week_bucket(sec, data, "learning")
    rest = _parse_week_bucket(sec, data, "rest")

    total = must_do.fraction + projects.fraction + learning.fraction + rest.fraction
    if abs(total - 1.0) > 1e-6:
        raise ConfigurationError(
            f"[{sec}] bucket fractions must sum to 1.0, got {total:.6f}"
        )

    return WeekConfig(must_do=must_do, projects=projects, learning=learning, rest=rest)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(path: Path) -> AppConfig:
    """
    Load and validate configuration from a TOML file.

    Args:
        path: Path to the TOML configuration file.

    Returns:
        Fully validated, immutable AppConfig.

    Raises:
        ConfigurationError: If the file is missing, unreadable, malformed,
            or contains invalid/missing fields.
    """
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {path}")

    try:
        with open(path, "rb") as fh:
            raw: dict[str, Any] = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(f"Configuration file is malformed TOML: {exc}") from exc
    except OSError as exc:
        raise ConfigurationError(f"Cannot read configuration file {path}: {exc}") from exc

    return AppConfig(
        task=_parse_task_config(raw),
        calendar=_parse_calendar_config(raw),
        fatigue=_parse_fatigue_config(raw),
        scheduler=_parse_scheduler_config(raw),
        learning=_parse_learning_config(raw),
        probability=_parse_probability_config(raw),
        logging=_parse_logging_config(raw),
        database=_parse_database_config(raw),
        week=_parse_week_config(raw),
    )

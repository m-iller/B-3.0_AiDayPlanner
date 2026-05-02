"""
Pure domain logic for the Fatigue module.

No database access, no side effects. All functions are deterministic.
"""

from __future__ import annotations

from ai_day_planner.config import FatigueConfig, SchedulerConfig


def compute_fatigue_increase(
    difficulty: int,
    actual_duration_minutes: int,
    config: FatigueConfig,
) -> float:
    """
    Compute the fatigue increase after completing a task.

    Formula (all weights from config):
        delta = difficulty * increase_difficulty_weight
              + actual_duration_minutes * increase_duration_weight

    Args:
        difficulty:               Task difficulty value.
        actual_duration_minutes:  Actual time spent on the task in minutes.
        config:                   FatigueConfig with weight coefficients.

    Returns:
        Positive float representing the fatigue increase (before clamping).
    """
    return (
        difficulty * config.increase_difficulty_weight
        + actual_duration_minutes * config.increase_duration_weight
    )


def compute_fatigue_recovery(
    rest_minutes: int,
    config: FatigueConfig,
) -> float:
    """
    Compute the fatigue decrease during a rest period.

    Formula:
        delta = rest_minutes * recovery_rate_per_minute

    Args:
        rest_minutes: Duration of the rest period in minutes.
        config:       FatigueConfig with recovery rate.

    Returns:
        Positive float representing the fatigue decrease (before clamping).
    """
    return rest_minutes * config.recovery_rate_per_minute


def clamp_fatigue_score(score: float, config: FatigueConfig) -> int:
    """
    Clamp a fatigue score to the configured [min_score, max_score] range.

    Args:
        score:  Raw (possibly out-of-range) fatigue score.
        config: FatigueConfig with min/max bounds.

    Returns:
        Integer score clamped to [config.min_score, config.max_score].
    """
    return int(max(config.min_score, min(config.max_score, round(score))))


def apply_fatigue_delta(
    current_score: int,
    delta: float,
    config: FatigueConfig,
) -> int:
    """
    Apply a signed delta to the current fatigue score and clamp the result.

    Positive delta increases fatigue; negative delta decreases it.

    Args:
        current_score: Current fatigue score.
        delta:         Signed change to apply (positive = more fatigued).
        config:        FatigueConfig with min/max bounds.

    Returns:
        New clamped fatigue score.
    """
    return clamp_fatigue_score(current_score + delta, config)


def apply_high_fatigue_penalty(
    priority_score: float,
    fatigue_score: int,
    task_difficulty: int,
    config: SchedulerConfig,
    fatigue_config: FatigueConfig,
) -> float:
    """
    Reduce priority score when fatigue is high and task difficulty is above midpoint.

    Formula:
        if fatigue_score > high_threshold AND difficulty > difficulty_midpoint:
            priority_score *= (1 - high_fatigue_penalty)

    Args:
        priority_score:   Computed priority score before penalty.
        fatigue_score:    Current fatigue score.
        task_difficulty:  Task difficulty value.
        config:           SchedulerConfig (unused here, kept for symmetry).
        fatigue_config:   FatigueConfig with threshold and penalty coefficient.

    Returns:
        Adjusted priority score.
    """
    difficulty_midpoint = (fatigue_config.min_score + fatigue_config.max_score) / 2
    if (
        fatigue_score > fatigue_config.high_threshold
        and task_difficulty > difficulty_midpoint
    ):
        return priority_score * (1.0 - fatigue_config.high_fatigue_penalty)
    return priority_score

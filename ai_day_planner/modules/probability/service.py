"""
Pure domain logic for the Probability module.

No database access, no side effects. All functions are deterministic.
"""

from __future__ import annotations

from datetime import time

from ai_day_planner.config import FatigueConfig, ProbabilityConfig, TaskConfig


# Time-of-day buckets: morning / afternoon / evening
# Each bucket maps to a factor in [0, 1] — higher = more productive
_TIME_OF_DAY_BUCKETS: list[tuple[int, int, float]] = [
    # (start_hour_inclusive, end_hour_exclusive, factor)
    (6,  12, 1.0),   # morning — peak productivity
    (12, 17, 0.85),  # afternoon — moderate
    (17, 21, 0.7),   # evening — lower
    (21, 24, 0.5),   # late night — low
    (0,   6, 0.4),   # early morning — very low
]


def _time_of_day_factor(slot_start: time) -> float:
    """Return a productivity factor in [0.4, 1.0] based on time of day."""
    hour = slot_start.hour
    for start, end, factor in _TIME_OF_DAY_BUCKETS:
        if start <= hour < end:
            return factor
    return 0.5  # fallback


def compute_completion_probability(
    fatigue_score: int,
    task_difficulty: int,
    slot_start: time,
    correction_coefficient: float,
    historical_completion_rate: float | None,
    config: ProbabilityConfig,
    fatigue_config: FatigueConfig,
    task_config: TaskConfig,
) -> float:
    """
    Compute the probability that a task will be completed in a given slot.

    Formula (weighted sum, normalized, clamped to [0.0, 1.0]):
        raw = w_fatigue     * (1 - fatigue_score / fatigue_max)
            + w_difficulty  * (1 - difficulty / difficulty_max)
            + w_time_of_day * time_of_day_factor(slot_start)
            + w_correction  * (1 / correction_coefficient)
            + w_historical  * historical_rate

        probability = clamp(raw / sum_of_weights, 0.0, 1.0)

    When historical_completion_rate is None, config.prior_probability is used.

    Args:
        fatigue_score:             Current fatigue score.
        task_difficulty:           Task difficulty value.
        slot_start:                Start time of the candidate slot.
        correction_coefficient:    EMA correction coefficient for the task.
        historical_completion_rate: Historical completion rate [0,1] or None.
        config:                    ProbabilityConfig with weights and prior.
        fatigue_config:            FatigueConfig for max_score.
        task_config:               TaskConfig for difficulty_max.

    Returns:
        Completion probability clamped to [0.0, 1.0].
    """
    historical_rate = (
        historical_completion_rate
        if historical_completion_rate is not None
        else config.prior_probability
    )

    # Guard against division by zero in correction component
    safe_correction = max(correction_coefficient, 1e-6)

    fatigue_component = 1.0 - fatigue_score / fatigue_config.max_score
    difficulty_component = 1.0 - task_difficulty / task_config.difficulty_max
    time_component = _time_of_day_factor(slot_start)
    correction_component = min(1.0 / safe_correction, 1.0)  # cap at 1.0
    historical_component = historical_rate

    raw = (
        config.weight_fatigue * fatigue_component
        + config.weight_difficulty * difficulty_component
        + config.weight_time_of_day * time_component
        + config.weight_correction * correction_component
        + config.weight_historical_rate * historical_component
    )

    total_weight = (
        config.weight_fatigue
        + config.weight_difficulty
        + config.weight_time_of_day
        + config.weight_correction
        + config.weight_historical_rate
    )

    normalized = raw / total_weight
    return max(0.0, min(1.0, normalized))


def compute_day_aggregate_probability(
    task_probabilities: list[float],
    config: ProbabilityConfig,
) -> float:
    """
    Compute the aggregate completion probability for a day.

    Uses the arithmetic mean of all per-task probabilities.
    Returns config.prior_probability when the list is empty.

    Args:
        task_probabilities: List of per-task completion probabilities.
        config:             ProbabilityConfig (provides prior for empty list).

    Returns:
        Aggregate probability clamped to [0.0, 1.0].
    """
    if not task_probabilities:
        return config.prior_probability

    mean = sum(task_probabilities) / len(task_probabilities)
    return max(0.0, min(1.0, mean))

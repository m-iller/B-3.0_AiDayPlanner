"""
Pure domain logic for the Learning module.

No database access, no side effects. All functions are deterministic.
"""

from __future__ import annotations


def compute_duration_ratio(
    actual_duration: int,
    estimated_duration: int,
) -> float:
    """
    Compute the ratio of actual to estimated task duration.

    Args:
        actual_duration:    Actual time spent in minutes.
        estimated_duration: Originally estimated time in minutes (must be > 0).

    Returns:
        Ratio actual / estimated. Values > 1.0 mean the task took longer than
        estimated; values < 1.0 mean it was faster.

    Raises:
        ValueError: If estimated_duration is zero or negative.
    """
    if estimated_duration <= 0:
        raise ValueError(
            f"estimated_duration must be > 0, got {estimated_duration}"
        )
    return actual_duration / estimated_duration


def compute_ema_coefficient(
    current_coefficient: float,
    new_ratio: float,
    alpha: float,
) -> float:
    """
    Update the correction coefficient using Exponential Moving Average.

    Formula:
        new_coefficient = alpha * new_ratio + (1 - alpha) * current_coefficient

    Args:
        current_coefficient: Current EMA coefficient value.
        new_ratio:           Latest observed actual/estimated duration ratio.
        alpha:               Smoothing factor in (0, 1]. Higher = more weight
                             on recent observations.

    Returns:
        Updated coefficient.

    Raises:
        ValueError: If alpha is not in (0, 1].
    """
    if not (0.0 < alpha <= 1.0):
        raise ValueError(f"alpha must be in (0, 1], got {alpha}")
    return alpha * new_ratio + (1.0 - alpha) * current_coefficient

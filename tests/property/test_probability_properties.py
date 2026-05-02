"""
Property-based tests for the Probability module.

Properties 23-24 from design.md, validated via Hypothesis.
"""

from __future__ import annotations

from datetime import time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ai_day_planner.config import FatigueConfig, ProbabilityConfig, TaskConfig
from ai_day_planner.modules.probability.service import (
    compute_completion_probability,
    compute_day_aggregate_probability,
)


def _make_prob_config() -> ProbabilityConfig:
    return ProbabilityConfig(
        prior_probability=0.7,
        weight_fatigue=0.25,
        weight_difficulty=0.25,
        weight_time_of_day=0.2,
        weight_correction=0.15,
        weight_historical_rate=0.15,
    )


def _make_fatigue_config() -> FatigueConfig:
    return FatigueConfig(
        min_score=1, max_score=100, high_threshold=75,
        increase_difficulty_weight=0.5, increase_duration_weight=0.05,
        recovery_rate_per_minute=0.1, high_fatigue_penalty=0.2,
    )


def _make_task_config() -> TaskConfig:
    return TaskConfig(
        difficulty_min=1, difficulty_max=10,
        urgency_min=1, urgency_max=10,
        importance_min=1, importance_max=10,
    )


# ---------------------------------------------------------------------------
# Property 23: Completion Probability Range Invariant
# ---------------------------------------------------------------------------

class TestProperty23CompletionProbabilityRange:
    """
    Property 23: Completion Probability Range Invariant

    For any combination of fatigue_score, task_difficulty, slot_start_time,
    correction_coefficient, and historical_completion_rate (or absent history),
    the computed Completion_Probability SHALL be in [0.0, 1.0] inclusive.

    Validates: Requirements 7.1, 7.7
    """

    @given(
        fatigue_score=st.integers(min_value=1, max_value=100),
        task_difficulty=st.integers(min_value=1, max_value=10),
        slot_hour=st.integers(min_value=0, max_value=23),
        correction=st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False),
        historical=st.one_of(
            st.none(),
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        ),
    )
    @settings(max_examples=100)
    def test_probability_in_range(
        self, fatigue_score, task_difficulty, slot_hour, correction, historical
    ):
        """Property 23: Completion Probability Range Invariant — Validates: Requirements 7.1, 7.7"""
        result = compute_completion_probability(
            fatigue_score=fatigue_score,
            task_difficulty=task_difficulty,
            slot_start=time(slot_hour, 0),
            correction_coefficient=correction,
            historical_completion_rate=historical,
            config=_make_prob_config(),
            fatigue_config=_make_fatigue_config(),
            task_config=_make_task_config(),
        )
        assert 0.0 <= result <= 1.0, (
            f"Probability {result} out of [0.0, 1.0] for inputs: "
            f"fatigue={fatigue_score}, difficulty={task_difficulty}, "
            f"hour={slot_hour}, correction={correction}, historical={historical}"
        )


# ---------------------------------------------------------------------------
# Property 24: Day Aggregate Probability Range
# ---------------------------------------------------------------------------

class TestProperty24DayAggregateProbabilityRange:
    """
    Property 24: Day Aggregate Probability Range

    For any list of per-task Completion_Probability values for a given day,
    the computed day aggregate probability SHALL be in [0.0, 1.0] inclusive.

    Validates: Requirements 7.2
    """

    @given(
        probabilities=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=0,
            max_size=20,
        )
    )
    @settings(max_examples=100)
    def test_aggregate_in_range(self, probabilities):
        """Property 24: Day Aggregate Probability Range — Validates: Requirements 7.2"""
        result = compute_day_aggregate_probability(probabilities, _make_prob_config())
        assert 0.0 <= result <= 1.0, (
            f"Aggregate {result} out of [0.0, 1.0] for probabilities: {probabilities}"
        )

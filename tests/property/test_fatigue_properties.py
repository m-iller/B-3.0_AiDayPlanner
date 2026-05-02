"""
Property-based tests for the Fatigue module.

Properties 17-19 from design.md, validated via Hypothesis.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ai_day_planner.config import FatigueConfig, SchedulerConfig
from ai_day_planner.modules.fatigue.service import (
    apply_fatigue_delta,
    apply_high_fatigue_penalty,
    clamp_fatigue_score,
    compute_fatigue_increase,
    compute_fatigue_recovery,
)


def _make_config(
    min_score: int = 1,
    max_score: int = 100,
    high_threshold: int = 75,
) -> FatigueConfig:
    return FatigueConfig(
        min_score=min_score,
        max_score=max_score,
        high_threshold=high_threshold,
        increase_difficulty_weight=0.5,
        increase_duration_weight=0.05,
        recovery_rate_per_minute=0.1,
        high_fatigue_penalty=0.2,
    )


def _make_scheduler_config() -> SchedulerConfig:
    return SchedulerConfig(
        weight_difficulty=1.0,
        weight_urgency=1.5,
        weight_importance=1.2,
        weight_fatigue=0.8,
        min_completion_probability=0.4,
        daily_overload_threshold=0.5,
    )


# ---------------------------------------------------------------------------
# Property 17: Fatigue Score Range Invariant
# ---------------------------------------------------------------------------

class TestProperty17FatigueScoreRangeInvariant:
    """
    Property 17: Fatigue Score Range Invariant

    For any sequence of fatigue update operations, the resulting Fatigue_Score
    SHALL always remain within [config.fatigue.min_score, config.fatigue.max_score].

    Validates: Requirements 4.1, 4.4
    """

    @given(
        current=st.integers(min_value=1, max_value=100),
        delta=st.floats(min_value=-200.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_apply_delta_stays_in_range(self, current, delta):
        """Property 17: Fatigue Score Range Invariant — Validates: Requirements 4.1, 4.4"""
        config = _make_config()
        result = apply_fatigue_delta(current, delta, config)
        assert config.min_score <= result <= config.max_score

    @given(
        score=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_clamp_always_in_range(self, score):
        """Property 17: Clamp always in range — Validates: Requirements 4.1, 4.4"""
        config = _make_config()
        result = clamp_fatigue_score(score, config)
        assert config.min_score <= result <= config.max_score

    @given(
        current=st.integers(min_value=1, max_value=100),
        difficulty=st.integers(min_value=1, max_value=10),
        duration=st.integers(min_value=0, max_value=480),
    )
    @settings(max_examples=100)
    def test_increase_then_clamp_in_range(self, current, difficulty, duration):
        """Property 17: Increase + clamp stays in range — Validates: Requirements 4.1, 4.4"""
        config = _make_config()
        delta = compute_fatigue_increase(difficulty, duration, config)
        result = apply_fatigue_delta(current, delta, config)
        assert config.min_score <= result <= config.max_score

    @given(
        current=st.integers(min_value=1, max_value=100),
        rest_minutes=st.integers(min_value=0, max_value=480),
    )
    @settings(max_examples=100)
    def test_recovery_then_clamp_in_range(self, current, rest_minutes):
        """Property 17: Recovery + clamp stays in range — Validates: Requirements 4.1, 4.4"""
        config = _make_config()
        delta = -compute_fatigue_recovery(rest_minutes, config)
        result = apply_fatigue_delta(current, delta, config)
        assert config.min_score <= result <= config.max_score


# ---------------------------------------------------------------------------
# Property 18: Fatigue Delta Formula Correctness
# ---------------------------------------------------------------------------

class TestProperty18FatigueDeltaFormula:
    """
    Property 18: Fatigue Delta Formula Correctness

    For any task completion with given difficulty and actual_duration_minutes,
    the fatigue increase SHALL equal:
        difficulty * increase_difficulty_weight + actual_duration_minutes * increase_duration_weight

    For any rest period of rest_minutes, the fatigue decrease SHALL equal:
        rest_minutes * recovery_rate_per_minute

    Both deltas SHALL use values sourced from Config.

    Validates: Requirements 4.2, 4.3
    """

    @given(
        difficulty=st.integers(min_value=0, max_value=20),
        duration=st.integers(min_value=0, max_value=480),
    )
    @settings(max_examples=100)
    def test_increase_formula_exact(self, difficulty, duration):
        """Property 18: Fatigue increase formula — Validates: Requirements 4.2"""
        config = _make_config()
        result = compute_fatigue_increase(difficulty, duration, config)
        expected = (
            difficulty * config.increase_difficulty_weight
            + duration * config.increase_duration_weight
        )
        assert abs(result - expected) < 1e-9

    @given(rest_minutes=st.integers(min_value=0, max_value=480))
    @settings(max_examples=100)
    def test_recovery_formula_exact(self, rest_minutes):
        """Property 18: Fatigue recovery formula — Validates: Requirements 4.3"""
        config = _make_config()
        result = compute_fatigue_recovery(rest_minutes, config)
        expected = rest_minutes * config.recovery_rate_per_minute
        assert abs(result - expected) < 1e-9


# ---------------------------------------------------------------------------
# Property 19: High-Fatigue Penalty Applied
# ---------------------------------------------------------------------------

class TestProperty19HighFatiguePenalty:
    """
    Property 19: High-Fatigue Penalty Applied

    For any task with difficulty > difficulty_midpoint and a fatigue score
    exceeding config.fatigue.high_threshold, the computed priority score SHALL
    be strictly less than the priority score computed at or below the threshold.

    Validates: Requirements 4.5
    """

    @given(
        base_priority=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        fatigue_above=st.integers(min_value=76, max_value=100),
        fatigue_below=st.integers(min_value=1, max_value=75),
        difficulty=st.integers(min_value=52, max_value=100),  # above midpoint of [1,100]
    )
    @settings(max_examples=100)
    def test_high_fatigue_reduces_priority(
        self, base_priority, fatigue_above, fatigue_below, difficulty
    ):
        """Property 19: High-Fatigue Penalty Applied — Validates: Requirements 4.5"""
        config = _make_config()
        scheduler_config = _make_scheduler_config()

        score_high_fatigue = apply_high_fatigue_penalty(
            base_priority, fatigue_above, difficulty, scheduler_config, config
        )
        score_low_fatigue = apply_high_fatigue_penalty(
            base_priority, fatigue_below, difficulty, scheduler_config, config
        )

        assert score_high_fatigue < score_low_fatigue

    @given(
        base_priority=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        fatigue_above=st.integers(min_value=76, max_value=100),
        difficulty_low=st.integers(min_value=1, max_value=50),  # at or below midpoint
    )
    @settings(max_examples=100)
    def test_no_penalty_for_low_difficulty(
        self, base_priority, fatigue_above, difficulty_low
    ):
        """Property 19: No penalty for low difficulty — Validates: Requirements 4.5"""
        config = _make_config()
        scheduler_config = _make_scheduler_config()

        result = apply_high_fatigue_penalty(
            base_priority, fatigue_above, difficulty_low, scheduler_config, config
        )
        assert abs(result - base_priority) < 1e-9

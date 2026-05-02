"""
Unit tests for ai_day_planner/modules/fatigue/service.py

Covers: compute_fatigue_increase, compute_fatigue_recovery,
        clamp_fatigue_score, apply_fatigue_delta, apply_high_fatigue_penalty.
"""

from __future__ import annotations

import pytest

from ai_day_planner.config import FatigueConfig, SchedulerConfig
from ai_day_planner.modules.fatigue.service import (
    apply_fatigue_delta,
    apply_high_fatigue_penalty,
    clamp_fatigue_score,
    compute_fatigue_increase,
    compute_fatigue_recovery,
)


@pytest.fixture()
def config() -> FatigueConfig:
    return FatigueConfig(
        min_score=1,
        max_score=100,
        high_threshold=75,
        increase_difficulty_weight=0.5,
        increase_duration_weight=0.05,
        recovery_rate_per_minute=0.1,
        high_fatigue_penalty=0.2,
    )


@pytest.fixture()
def scheduler_config() -> SchedulerConfig:
    return SchedulerConfig(
        weight_difficulty=1.0,
        weight_urgency=1.5,
        weight_importance=1.2,
        weight_fatigue=0.8,
        min_completion_probability=0.4,
        daily_overload_threshold=0.5,
    )


class TestComputeFatigueIncrease:
    def test_formula_correctness(self, config):
        result = compute_fatigue_increase(5, 60, config)
        expected = 5 * 0.5 + 60 * 0.05
        assert abs(result - expected) < 1e-9

    def test_zero_duration_only_difficulty_component(self, config):
        result = compute_fatigue_increase(8, 0, config)
        assert abs(result - 8 * 0.5) < 1e-9

    def test_zero_difficulty_only_duration_component(self, config):
        result = compute_fatigue_increase(0, 120, config)
        assert abs(result - 120 * 0.05) < 1e-9

    def test_higher_difficulty_increases_result(self, config):
        low = compute_fatigue_increase(2, 30, config)
        high = compute_fatigue_increase(9, 30, config)
        assert high > low

    def test_longer_duration_increases_result(self, config):
        short = compute_fatigue_increase(5, 15, config)
        long_ = compute_fatigue_increase(5, 120, config)
        assert long_ > short

    def test_returns_float(self, config):
        assert isinstance(compute_fatigue_increase(5, 30, config), float)


class TestComputeFatigueRecovery:
    def test_formula_correctness(self, config):
        result = compute_fatigue_recovery(60, config)
        assert abs(result - 60 * 0.1) < 1e-9

    def test_zero_rest_returns_zero(self, config):
        assert compute_fatigue_recovery(0, config) == 0.0

    def test_longer_rest_more_recovery(self, config):
        assert compute_fatigue_recovery(120, config) > compute_fatigue_recovery(30, config)

    def test_returns_float(self, config):
        assert isinstance(compute_fatigue_recovery(30, config), float)


class TestClampFatigueScore:
    def test_within_range_unchanged(self, config):
        assert clamp_fatigue_score(50.0, config) == 50

    def test_below_min_clamped_to_min(self, config):
        assert clamp_fatigue_score(-10.0, config) == 1

    def test_above_max_clamped_to_max(self, config):
        assert clamp_fatigue_score(150.0, config) == 100

    def test_exactly_min_returns_min(self, config):
        assert clamp_fatigue_score(1.0, config) == 1

    def test_exactly_max_returns_max(self, config):
        assert clamp_fatigue_score(100.0, config) == 100

    def test_returns_int(self, config):
        assert isinstance(clamp_fatigue_score(50.0, config), int)


class TestApplyFatigueDelta:
    def test_positive_delta_increases_score(self, config):
        result = apply_fatigue_delta(50, 10.0, config)
        assert result == 60

    def test_negative_delta_decreases_score(self, config):
        result = apply_fatigue_delta(50, -10.0, config)
        assert result == 40

    def test_clamped_at_max(self, config):
        result = apply_fatigue_delta(95, 20.0, config)
        assert result == 100

    def test_clamped_at_min(self, config):
        result = apply_fatigue_delta(5, -20.0, config)
        assert result == 1

    def test_zero_delta_unchanged(self, config):
        assert apply_fatigue_delta(50, 0.0, config) == 50


class TestApplyHighFatiguePenalty:
    def test_no_penalty_below_threshold(self, config, scheduler_config):
        # fatigue 50 < threshold 75 — no penalty
        score = apply_high_fatigue_penalty(100.0, 50, 8, scheduler_config, config)
        assert score == 100.0

    def test_penalty_applied_above_threshold_high_difficulty(self, config, scheduler_config):
        # fatigue 80 > threshold 75, difficulty 60 > midpoint 50.5 (midpoint of [1,100])
        score = apply_high_fatigue_penalty(100.0, 80, 60, scheduler_config, config)
        assert abs(score - 80.0) < 1e-9  # 100 * (1 - 0.2)

    def test_no_penalty_above_threshold_low_difficulty(self, config, scheduler_config):
        # fatigue 80 > threshold, but difficulty 30 < midpoint 50.5
        score = apply_high_fatigue_penalty(100.0, 80, 30, scheduler_config, config)
        assert score == 100.0

    def test_penalty_reduces_score(self, config, scheduler_config):
        # difficulty 60 > midpoint 50.5, fatigue 80 > threshold 75
        penalized = apply_high_fatigue_penalty(100.0, 80, 60, scheduler_config, config)
        assert penalized < 100.0

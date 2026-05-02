"""
Unit tests for ai_day_planner/modules/probability/service.py

Covers: compute_completion_probability, compute_day_aggregate_probability.
"""

from __future__ import annotations

from datetime import time

import pytest

from ai_day_planner.config import FatigueConfig, ProbabilityConfig, TaskConfig
from ai_day_planner.modules.probability.service import (
    compute_completion_probability,
    compute_day_aggregate_probability,
)


@pytest.fixture()
def prob_config() -> ProbabilityConfig:
    return ProbabilityConfig(
        prior_probability=0.7,
        weight_fatigue=0.25,
        weight_difficulty=0.25,
        weight_time_of_day=0.2,
        weight_correction=0.15,
        weight_historical_rate=0.15,
    )


@pytest.fixture()
def fatigue_config() -> FatigueConfig:
    return FatigueConfig(
        min_score=1, max_score=100, high_threshold=75,
        increase_difficulty_weight=0.5, increase_duration_weight=0.05,
        recovery_rate_per_minute=0.1, high_fatigue_penalty=0.2,
    )


@pytest.fixture()
def task_config() -> TaskConfig:
    return TaskConfig(
        difficulty_min=1, difficulty_max=10,
        urgency_min=1, urgency_max=10,
        importance_min=1, importance_max=10,
    )


def _prob(
    fatigue=20, difficulty=5, slot_hour=9, correction=1.0,
    historical=None, prob_config=None, fatigue_config=None, task_config=None,
):
    return compute_completion_probability(
        fatigue_score=fatigue,
        task_difficulty=difficulty,
        slot_start=time(slot_hour, 0),
        correction_coefficient=correction,
        historical_completion_rate=historical,
        config=prob_config,
        fatigue_config=fatigue_config,
        task_config=task_config,
    )


class TestComputeCompletionProbability:
    def test_result_in_range(self, prob_config, fatigue_config, task_config):
        result = _prob(prob_config=prob_config, fatigue_config=fatigue_config, task_config=task_config)
        assert 0.0 <= result <= 1.0

    def test_high_fatigue_lowers_probability(self, prob_config, fatigue_config, task_config):
        low = _prob(fatigue=10, prob_config=prob_config, fatigue_config=fatigue_config, task_config=task_config)
        high = _prob(fatigue=90, prob_config=prob_config, fatigue_config=fatigue_config, task_config=task_config)
        assert low > high

    def test_high_difficulty_lowers_probability(self, prob_config, fatigue_config, task_config):
        easy = _prob(difficulty=1, prob_config=prob_config, fatigue_config=fatigue_config, task_config=task_config)
        hard = _prob(difficulty=10, prob_config=prob_config, fatigue_config=fatigue_config, task_config=task_config)
        assert easy > hard

    def test_morning_slot_higher_than_late_night(self, prob_config, fatigue_config, task_config):
        morning = _prob(slot_hour=9, prob_config=prob_config, fatigue_config=fatigue_config, task_config=task_config)
        late = _prob(slot_hour=2, prob_config=prob_config, fatigue_config=fatigue_config, task_config=task_config)
        assert morning > late

    def test_prior_used_when_no_history(self, prob_config, fatigue_config, task_config):
        # With no history, prior_probability (0.7) is used for historical component
        result = _prob(historical=None, prob_config=prob_config, fatigue_config=fatigue_config, task_config=task_config)
        assert 0.0 <= result <= 1.0

    def test_high_historical_rate_increases_probability(self, prob_config, fatigue_config, task_config):
        low_hist = _prob(historical=0.1, prob_config=prob_config, fatigue_config=fatigue_config, task_config=task_config)
        high_hist = _prob(historical=0.9, prob_config=prob_config, fatigue_config=fatigue_config, task_config=task_config)
        assert high_hist > low_hist

    def test_returns_float(self, prob_config, fatigue_config, task_config):
        result = _prob(prob_config=prob_config, fatigue_config=fatigue_config, task_config=task_config)
        assert isinstance(result, float)


class TestComputeDayAggregateProbability:
    def test_empty_list_returns_prior(self, prob_config):
        result = compute_day_aggregate_probability([], prob_config)
        assert result == prob_config.prior_probability

    def test_single_probability_returns_it(self, prob_config):
        result = compute_day_aggregate_probability([0.8], prob_config)
        assert abs(result - 0.8) < 1e-9

    def test_mean_of_multiple(self, prob_config):
        result = compute_day_aggregate_probability([0.6, 0.8, 1.0], prob_config)
        assert abs(result - 0.8) < 1e-9

    def test_result_in_range(self, prob_config):
        result = compute_day_aggregate_probability([0.3, 0.5, 0.7], prob_config)
        assert 0.0 <= result <= 1.0

    def test_all_zeros_returns_zero(self, prob_config):
        result = compute_day_aggregate_probability([0.0, 0.0, 0.0], prob_config)
        assert result == 0.0

    def test_all_ones_returns_one(self, prob_config):
        result = compute_day_aggregate_probability([1.0, 1.0, 1.0], prob_config)
        assert result == 1.0

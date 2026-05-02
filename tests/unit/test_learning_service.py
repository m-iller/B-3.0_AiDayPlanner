"""
Unit tests for ai_day_planner/modules/learning/service.py

Covers: compute_duration_ratio, compute_ema_coefficient.
"""

from __future__ import annotations

import pytest

from ai_day_planner.modules.learning.service import (
    compute_duration_ratio,
    compute_ema_coefficient,
)


class TestComputeDurationRatio:
    def test_equal_durations_returns_one(self):
        assert compute_duration_ratio(60, 60) == 1.0

    def test_actual_longer_returns_above_one(self):
        assert compute_duration_ratio(90, 60) == 1.5

    def test_actual_shorter_returns_below_one(self):
        assert compute_duration_ratio(30, 60) == 0.5

    def test_zero_estimated_raises(self):
        with pytest.raises(ValueError, match="estimated_duration"):
            compute_duration_ratio(60, 0)

    def test_negative_estimated_raises(self):
        with pytest.raises(ValueError):
            compute_duration_ratio(60, -10)

    def test_returns_float(self):
        assert isinstance(compute_duration_ratio(45, 30), float)

    def test_formula_correctness(self):
        result = compute_duration_ratio(75, 50)
        assert abs(result - 1.5) < 1e-9


class TestComputeEmaCoefficient:
    def test_formula_correctness(self):
        result = compute_ema_coefficient(1.0, 2.0, 0.3)
        expected = 0.3 * 2.0 + 0.7 * 1.0
        assert abs(result - expected) < 1e-9

    def test_alpha_one_returns_new_ratio(self):
        result = compute_ema_coefficient(1.0, 2.5, 1.0)
        assert abs(result - 2.5) < 1e-9

    def test_alpha_near_zero_stays_near_current(self):
        result = compute_ema_coefficient(1.0, 100.0, 0.01)
        assert result < 2.0  # barely moved

    def test_invalid_alpha_zero_raises(self):
        with pytest.raises(ValueError, match="alpha"):
            compute_ema_coefficient(1.0, 2.0, 0.0)

    def test_invalid_alpha_above_one_raises(self):
        with pytest.raises(ValueError):
            compute_ema_coefficient(1.0, 2.0, 1.5)

    def test_converges_toward_constant_ratio(self):
        """After many updates with ratio=2.0, coefficient should approach 2.0."""
        coeff = 1.0
        for _ in range(200):
            coeff = compute_ema_coefficient(coeff, 2.0, 0.3)
        assert abs(coeff - 2.0) < 0.01

    def test_returns_float(self):
        assert isinstance(compute_ema_coefficient(1.0, 1.5, 0.3), float)

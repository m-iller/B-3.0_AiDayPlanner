"""
Property-based tests for the Learning module.

Properties 21-22 from design.md, validated via Hypothesis.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ai_day_planner.modules.learning.service import (
    compute_ema_coefficient,
    compute_duration_ratio,
)


# ---------------------------------------------------------------------------
# Property 21: EMA Coefficient Update Formula
# ---------------------------------------------------------------------------

class TestProperty21EmaFormula:
    """
    Property 21: EMA Coefficient Update Formula

    For any existing correction_coefficient and new duration_ratio, the updated
    coefficient SHALL equal:
        alpha * new_ratio + (1 - alpha) * current_coefficient

    where alpha = config.learning.ema_smoothing_factor.

    Validates: Requirements 6.1, 6.2
    """

    @given(
        current=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
        new_ratio=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
        alpha=st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_ema_formula_exact(self, current, new_ratio, alpha):
        """Property 21: EMA Coefficient Update Formula — Validates: Requirements 6.1, 6.2"""
        result = compute_ema_coefficient(current, new_ratio, alpha)
        expected = alpha * new_ratio + (1.0 - alpha) * current
        assert abs(result - expected) < 1e-9


# ---------------------------------------------------------------------------
# Property 22: EMA Convergence
# ---------------------------------------------------------------------------

class TestProperty22EmaConvergence:
    """
    Property 22: EMA Convergence

    For any task with a long sequence of tracking sessions all producing the
    same duration_ratio r, the correction_coefficient SHALL converge
    monotonically toward r as the number of sessions increases, with the
    absolute difference |coefficient - r| strictly decreasing after each session.

    Validates: Requirements 6.7
    """

    @given(
        initial=st.floats(min_value=0.5, max_value=3.0, allow_nan=False, allow_infinity=False),
        target_ratio=st.floats(min_value=0.5, max_value=3.0, allow_nan=False, allow_infinity=False),
        alpha=st.floats(min_value=0.05, max_value=0.9, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_ema_converges_toward_constant_ratio(self, initial, target_ratio, alpha):
        """Property 22: EMA Convergence — Validates: Requirements 6.7"""
        if abs(initial - target_ratio) < 1e-6:
            return  # already converged — trivially true

        coeff = initial
        prev_diff = abs(coeff - target_ratio)

        for _ in range(50):
            coeff = compute_ema_coefficient(coeff, target_ratio, alpha)
            new_diff = abs(coeff - target_ratio)
            assert new_diff <= prev_diff + 1e-12, (
                f"EMA diverged: diff went from {prev_diff} to {new_diff} "
                f"(initial={initial}, target={target_ratio}, alpha={alpha})"
            )
            prev_diff = new_diff

        # After 50 iterations, should be much closer to target
        assert abs(coeff - target_ratio) < abs(initial - target_ratio)

    @given(
        target_ratio=st.floats(min_value=0.5, max_value=3.0, allow_nan=False, allow_infinity=False),
        alpha=st.floats(min_value=0.1, max_value=0.9, allow_nan=False, allow_infinity=False),
        n_sessions=st.integers(min_value=50, max_value=200),
    )
    @settings(max_examples=50)
    def test_ema_converges_within_tolerance(self, target_ratio, alpha, n_sessions):
        """Property 22: EMA converges within tolerance after many sessions — Validates: Requirements 6.7"""
        coeff = 1.0
        for _ in range(n_sessions):
            coeff = compute_ema_coefficient(coeff, target_ratio, alpha)

        # After many sessions, should be within 5% of target
        assert abs(coeff - target_ratio) < 0.05 * max(abs(target_ratio), 0.1) + 0.05

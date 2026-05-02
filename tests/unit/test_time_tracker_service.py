"""
Unit tests for ai_day_planner/modules/time_tracker/service.py

Covers: compute_actual_duration, validate_state_transition.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from ai_day_planner.modules.tasks.models import TaskState
from ai_day_planner.modules.time_tracker.models import Interruption, TrackingAction
from ai_day_planner.modules.time_tracker.service import (
    compute_actual_duration,
    validate_state_transition,
)


def _dt(offset_minutes: int = 0) -> datetime:
    base = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(minutes=offset_minutes)


def _interruption(start_offset: int, end_offset: int | None) -> Interruption:
    end = _dt(end_offset) if end_offset is not None else None
    return Interruption(
        id=str(uuid.uuid4()),
        session_id="s1",
        start_time=_dt(start_offset),
        end_time=end,
        duration_minutes=(end_offset - start_offset) if end_offset is not None else None,
    )


# ---------------------------------------------------------------------------
# compute_actual_duration
# ---------------------------------------------------------------------------

class TestComputeActualDuration:
    def test_no_interruptions(self):
        result = compute_actual_duration(_dt(0), _dt(60), [])
        assert result == 60

    def test_single_interruption(self):
        # 60 min session, 10 min interruption → 50 min actual
        result = compute_actual_duration(
            _dt(0), _dt(60), [_interruption(20, 30)]
        )
        assert result == 50

    def test_multiple_interruptions(self):
        # 120 min session, 10+15=25 min interruptions → 95 min actual
        result = compute_actual_duration(
            _dt(0), _dt(120),
            [_interruption(10, 20), _interruption(50, 65)],
        )
        assert result == 95

    def test_open_interruption_ignored(self):
        # Open interruption (no end_time) should not reduce duration
        result = compute_actual_duration(
            _dt(0), _dt(60), [_interruption(30, None)]
        )
        assert result == 60

    def test_zero_duration_session(self):
        result = compute_actual_duration(_dt(0), _dt(0), [])
        assert result == 0

    def test_returns_whole_minutes(self):
        # 90 seconds = 1 minute (floor)
        start = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 9, 1, 30, tzinfo=timezone.utc)
        result = compute_actual_duration(start, end, [])
        assert result == 1

    def test_result_never_negative(self):
        # Interruptions longer than session → clamped to 0
        result = compute_actual_duration(
            _dt(0), _dt(10), [_interruption(0, 60)]
        )
        assert result == 0


# ---------------------------------------------------------------------------
# validate_state_transition
# ---------------------------------------------------------------------------

class TestValidateStateTransition:
    # Valid transitions
    def test_pending_start_valid(self):
        assert validate_state_transition(TaskState.pending, TrackingAction.start) is True

    def test_in_progress_stop_valid(self):
        assert validate_state_transition(TaskState.in_progress, TrackingAction.stop) is True

    def test_in_progress_interrupt_start_valid(self):
        assert validate_state_transition(TaskState.in_progress, TrackingAction.interrupt_start) is True

    def test_interrupted_interrupt_end_valid(self):
        assert validate_state_transition(TaskState.interrupted, TrackingAction.interrupt_end) is True

    def test_interrupted_stop_valid(self):
        assert validate_state_transition(TaskState.interrupted, TrackingAction.stop) is True

    # Invalid transitions
    def test_pending_stop_invalid(self):
        assert validate_state_transition(TaskState.pending, TrackingAction.stop) is False

    def test_pending_interrupt_start_invalid(self):
        assert validate_state_transition(TaskState.pending, TrackingAction.interrupt_start) is False

    def test_in_progress_start_invalid(self):
        assert validate_state_transition(TaskState.in_progress, TrackingAction.start) is False

    def test_in_progress_interrupt_end_invalid(self):
        assert validate_state_transition(TaskState.in_progress, TrackingAction.interrupt_end) is False

    def test_interrupted_start_invalid(self):
        assert validate_state_transition(TaskState.interrupted, TrackingAction.start) is False

    def test_interrupted_interrupt_start_invalid(self):
        assert validate_state_transition(TaskState.interrupted, TrackingAction.interrupt_start) is False

    def test_completed_all_actions_invalid(self):
        for action in TrackingAction:
            assert validate_state_transition(TaskState.completed, action) is False

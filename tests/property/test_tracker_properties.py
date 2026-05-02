"""
Property-based tests for the Time Tracker module.

Property 20 from design.md, validated via Hypothesis.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ai_day_planner.modules.time_tracker.models import Interruption
from ai_day_planner.modules.time_tracker.service import compute_actual_duration


def _make_interruption(
    start_offset_min: int,
    end_offset_min: int,
) -> Interruption:
    base = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
    start = base + timedelta(minutes=start_offset_min)
    end = base + timedelta(minutes=end_offset_min)
    return Interruption(
        id=str(uuid.uuid4()),
        session_id="s1",
        start_time=start,
        end_time=end,
        duration_minutes=end_offset_min - start_offset_min,
    )


# ---------------------------------------------------------------------------
# Property 20: Actual Duration Computation
# ---------------------------------------------------------------------------

class TestProperty20ActualDurationComputation:
    """
    Property 20: Actual Duration Computation

    For any tracking session with start_time, end_time, and a list of
    interruptions (each with start_time and end_time), the computed
    actual_duration SHALL equal:
        (end_time - start_time) - sum(interruption.end_time - interruption.start_time)
    expressed in whole minutes.

    Validates: Requirements 5.3, 5.6
    """

    @given(
        session_duration=st.integers(min_value=0, max_value=480),
        interruption_durations=st.lists(
            st.integers(min_value=1, max_value=30),
            min_size=0,
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_actual_duration_formula(self, session_duration, interruption_durations):
        """Property 20: Actual Duration Computation — Validates: Requirements 5.3, 5.6"""
        base = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        start = base
        end = base + timedelta(minutes=session_duration)

        # Build non-overlapping interruptions within the session
        interruptions = []
        cursor = 0
        for dur in interruption_durations:
            if cursor + dur > session_duration:
                break
            interruptions.append(_make_interruption(cursor, cursor + dur))
            cursor += dur + 1  # 1-minute gap between interruptions

        total_interruption = sum(
            (intr.end_time - intr.start_time).total_seconds() / 60
            for intr in interruptions
            if intr.end_time is not None
        )
        expected = max(0, int((session_duration - total_interruption)))

        result = compute_actual_duration(start, end, interruptions)
        assert result == expected, (
            f"Expected {expected}, got {result} "
            f"(session={session_duration}min, interruptions={[i.duration_minutes for i in interruptions]})"
        )

    @given(
        session_duration=st.integers(min_value=1, max_value=480),
    )
    @settings(max_examples=100)
    def test_result_never_negative(self, session_duration):
        """Property 20: Result never negative — Validates: Requirements 5.3"""
        base = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        start = base
        end = base + timedelta(minutes=session_duration)
        # Interruption longer than session
        interruptions = [_make_interruption(0, session_duration + 60)]
        result = compute_actual_duration(start, end, interruptions)
        assert result >= 0

    @given(
        session_duration=st.integers(min_value=1, max_value=480),
    )
    @settings(max_examples=100)
    def test_no_interruptions_equals_session_duration(self, session_duration):
        """Property 20: No interruptions = full session duration — Validates: Requirements 5.3"""
        base = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        result = compute_actual_duration(base, base + timedelta(minutes=session_duration), [])
        assert result == session_duration

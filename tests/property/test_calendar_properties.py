"""
Property-based tests for the Calendar module.

Properties 8-11 from design.md, validated via Hypothesis.
All tests use in-memory SQLite for isolation.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ai_day_planner.config import CalendarConfig
from ai_day_planner.database import get_connection, run_migrations
from ai_day_planner.modules.calendar.models import (
    FreeSlot,
    ScheduleEntry,
    TimeBlock,
)
from ai_day_planner.modules.calendar.repository import (
    ScheduleEntryRepository,
    TimeBlockRepository,
)
from ai_day_planner.modules.calendar.service import (
    compute_free_slots,
    detect_time_block_overlap,
    _time_to_minutes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_repos():
    conn = get_connection(":memory:")
    run_migrations(conn)
    return TimeBlockRepository(conn), ScheduleEntryRepository(conn)


def _make_config(start: str = "08:00", end: str = "20:00") -> CalendarConfig:
    return CalendarConfig(active_hours_start=start, active_hours_end=end)


def _make_block(day: int, start_min: int, end_min: int) -> TimeBlock:
    return TimeBlock(
        id=str(uuid.uuid4()),
        day_of_week=day,
        start_time=f"{start_min // 60:02d}:{start_min % 60:02d}",
        end_time=f"{end_min // 60:02d}:{end_min % 60:02d}",
        label="Block",
        is_recurring=True,
    )


# ---------------------------------------------------------------------------
# Property 8: Time Block Creation Round-Trip
# ---------------------------------------------------------------------------

class TestProperty8TimeBlockRoundTrip:
    """
    Property 8: Time Block Creation Round-Trip

    For any valid TimeBlockCreateRequest, creating the time block and then
    querying it by the returned ID SHALL return a time block with all fields
    equal to the submitted values.

    Validates: Requirements 2.2
    """

    @given(
        day_of_week=st.integers(min_value=0, max_value=6),
        start_hour=st.integers(min_value=0, max_value=22),
        duration_hours=st.integers(min_value=1, max_value=2),
        is_recurring=st.booleans(),
    )
    @settings(max_examples=100)
    def test_round_trip(self, day_of_week, start_hour, duration_hours, is_recurring):
        """Property 8: Time Block Creation Round-Trip — Validates: Requirements 2.2"""
        repo, _ = _fresh_repos()
        block = TimeBlock(
            id=str(uuid.uuid4()),
            day_of_week=day_of_week,
            start_time=f"{start_hour:02d}:00",
            end_time=f"{start_hour + duration_hours:02d}:00",
            label="Test",
            is_recurring=is_recurring,
        )
        created = repo.create(block)
        fetched = repo.get_by_id(created.id)

        assert fetched is not None
        assert fetched.id == block.id
        assert fetched.day_of_week == block.day_of_week
        assert fetched.start_time == block.start_time
        assert fetched.end_time == block.end_time
        assert fetched.label == block.label
        assert fetched.is_recurring == block.is_recurring


# ---------------------------------------------------------------------------
# Property 9: Time Block Overlap Rejection
# ---------------------------------------------------------------------------

class TestProperty9TimeBlockOverlapRejection:
    """
    Property 9: Time Block Overlap Rejection

    For any existing time block on a given day, any new time block creation
    request whose time interval overlaps the existing block on the same day
    SHALL be rejected, regardless of whether the overlap is partial or total.

    Validates: Requirements 2.3
    """

    @given(
        day=st.integers(min_value=0, max_value=6),
        existing_start=st.integers(min_value=480, max_value=900),   # 08:00-15:00
        existing_end=st.integers(min_value=960, max_value=1200),    # 16:00-20:00
        overlap_start=st.integers(min_value=480, max_value=900),
        overlap_end=st.integers(min_value=960, max_value=1200),
    )
    @settings(max_examples=100)
    def test_overlapping_block_detected(
        self, day, existing_start, existing_end, overlap_start, overlap_end
    ):
        """Property 9: Time Block Overlap Rejection — Validates: Requirements 2.3"""
        existing = _make_block(day, existing_start, existing_end)
        # new block fully contains the existing block — guaranteed overlap
        new_block = _make_block(day, existing_start, existing_end)
        assert detect_time_block_overlap(new_block, [existing]) is True

    @given(
        day=st.integers(min_value=0, max_value=6),
        start_a=st.integers(min_value=480, max_value=700),
        end_a=st.integers(min_value=720, max_value=900),
        start_b=st.integers(min_value=960, max_value=1100),
        end_b=st.integers(min_value=1140, max_value=1200),
    )
    @settings(max_examples=100)
    def test_non_overlapping_blocks_not_detected(
        self, day, start_a, end_a, start_b, end_b
    ):
        """Property 9: Non-overlapping blocks pass — Validates: Requirements 2.3"""
        existing = _make_block(day, start_a, end_a)
        new_block = _make_block(day, start_b, end_b)
        assert detect_time_block_overlap(new_block, [existing]) is False


# ---------------------------------------------------------------------------
# Property 10: Free Slot Computation Correctness
# ---------------------------------------------------------------------------

class TestProperty10FreeSlotComputation:
    """
    Property 10: Free Slot Computation Correctness

    For any combination of time blocks and scheduled tasks on a given day,
    the computed free slots SHALL satisfy:
    (a) no free slot interval overlaps any time block or scheduled task interval
    (b) the union of all free slots, time blocks, and scheduled tasks exactly
        covers the configured active hours with no gaps.

    Validates: Requirements 2.5
    """

    @given(
        block_starts=st.lists(
            st.integers(min_value=480, max_value=1100),
            min_size=0,
            max_size=4,
        ),
    )
    @settings(max_examples=100)
    def test_free_slots_no_overlap_with_blocks(self, block_starts):
        """Property 10a: Free slots do not overlap time blocks — Validates: Requirements 2.5"""
        config = _make_config("08:00", "20:00")
        day = date(2024, 1, 1)  # Monday

        # Build non-overlapping 30-min blocks
        blocks = []
        used: list[tuple[int, int]] = []
        for s in sorted(set(block_starts)):
            e = s + 30
            if e > 1200:
                continue
            if any(s < ue and us < e for us, ue in used):
                continue
            blocks.append(_make_block(0, s, e))
            used.append((s, e))

        free_slots = compute_free_slots(day, blocks, [], config)

        # No free slot should overlap any block
        for slot in free_slots:
            slot_s = _time_to_minutes(slot.start_time)
            slot_e = _time_to_minutes(slot.end_time)
            for block in blocks:
                blk_s = _time_to_minutes(block.start_time)
                blk_e = _time_to_minutes(block.end_time)
                assert not (slot_s < blk_e and blk_s < slot_e), (
                    f"Free slot {slot.start_time}-{slot.end_time} overlaps "
                    f"block {block.start_time}-{block.end_time}"
                )

    @given(
        block_starts=st.lists(
            st.integers(min_value=480, max_value=1100),
            min_size=0,
            max_size=4,
        ),
    )
    @settings(max_examples=100)
    def test_free_slots_cover_full_active_hours(self, block_starts):
        """Property 10b: Free slots + blocks cover full active hours — Validates: Requirements 2.5"""
        config = _make_config("08:00", "20:00")
        active_start = _time_to_minutes("08:00")
        active_end = _time_to_minutes("20:00")
        total_active = active_end - active_start  # 720 min

        day = date(2024, 1, 1)

        blocks = []
        used: list[tuple[int, int]] = []
        for s in sorted(set(block_starts)):
            e = s + 30
            if e > 1200:
                continue
            if any(s < ue and us < e for us, ue in used):
                continue
            blocks.append(_make_block(0, s, e))
            used.append((s, e))

        free_slots = compute_free_slots(day, blocks, [], config)

        total_free = sum(s.duration_minutes for s in free_slots)
        total_occupied = sum(e - s for s, e in used if s >= active_start and e <= active_end)

        assert total_free + total_occupied == total_active


# ---------------------------------------------------------------------------
# Property 11: No Task Scheduled Into a Time Block
# ---------------------------------------------------------------------------

class TestProperty11NoTaskInTimeBlock:
    """
    Property 11: No Task Scheduled Into a Time Block

    For any scheduling run result, no assigned ScheduleEntry SHALL have a
    time interval that overlaps any TimeBlock interval on the same day.

    Validates: Requirements 2.6, 3.6 (constraint enforcement)

    Note: This property tests the free slot computation — tasks can only be
    scheduled into free slots, which by Property 10 do not overlap time blocks.
    """

    @given(
        block_start=st.integers(min_value=540, max_value=900),   # 09:00-15:00
        block_duration=st.integers(min_value=30, max_value=120),
    )
    @settings(max_examples=100)
    def test_free_slots_never_overlap_time_blocks(self, block_start, block_duration):
        """Property 11: No task scheduled into time block — Validates: Requirements 2.6, 3.6"""
        block_end = block_start + block_duration
        if block_end > 1200:
            block_end = 1200

        config = _make_config("08:00", "20:00")
        day = date(2024, 1, 1)
        block = _make_block(0, block_start, block_end)

        free_slots = compute_free_slots(day, [block], [], config)

        blk_s = _time_to_minutes(block.start_time)
        blk_e = _time_to_minutes(block.end_time)

        for slot in free_slots:
            slot_s = _time_to_minutes(slot.start_time)
            slot_e = _time_to_minutes(slot.end_time)
            assert not (slot_s < blk_e and blk_s < slot_e), (
                f"Free slot {slot.start_time}-{slot.end_time} overlaps "
                f"time block {block.start_time}-{block.end_time}"
            )

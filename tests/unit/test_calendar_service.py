"""
Unit tests for ai_day_planner/modules/calendar/service.py

Covers: detect_time_block_overlap, compute_free_slots.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from ai_day_planner.config import CalendarConfig
from ai_day_planner.modules.calendar.models import (
    FreeSlot,
    ScheduleEntry,
    TimeBlock,
)
from ai_day_planner.modules.calendar.service import (
    compute_free_slots,
    detect_time_block_overlap,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def config() -> CalendarConfig:
    return CalendarConfig(active_hours_start="08:00", active_hours_end="20:00")


def _block(day: int, start: str, end: str, block_id: str | None = None) -> TimeBlock:
    return TimeBlock(
        id=block_id or str(uuid.uuid4()),
        day_of_week=day,
        start_time=start,
        end_time=end,
        label="Test Block",
        is_recurring=True,
    )


def _entry(day: date, start: str, end: str) -> ScheduleEntry:
    return ScheduleEntry(
        id=str(uuid.uuid4()),
        task_id=str(uuid.uuid4()),
        scheduled_date=day,
        slot_start=start,
        slot_end=end,
        is_confirmed=False,
    )


# ---------------------------------------------------------------------------
# detect_time_block_overlap
# ---------------------------------------------------------------------------

class TestDetectTimeBlockOverlap:
    def test_no_existing_blocks_no_overlap(self):
        new = _block(0, "09:00", "10:00")
        assert detect_time_block_overlap(new, []) is False

    def test_identical_block_overlaps(self):
        existing = _block(0, "09:00", "10:00")
        new = _block(0, "09:00", "10:00")
        assert detect_time_block_overlap(new, [existing]) is True

    def test_partial_overlap_start(self):
        existing = _block(0, "09:00", "11:00")
        new = _block(0, "08:00", "10:00")
        assert detect_time_block_overlap(new, [existing]) is True

    def test_partial_overlap_end(self):
        existing = _block(0, "09:00", "11:00")
        new = _block(0, "10:00", "12:00")
        assert detect_time_block_overlap(new, [existing]) is True

    def test_contained_within_existing(self):
        existing = _block(0, "09:00", "12:00")
        new = _block(0, "10:00", "11:00")
        assert detect_time_block_overlap(new, [existing]) is True

    def test_adjacent_no_overlap(self):
        existing = _block(0, "09:00", "10:00")
        new = _block(0, "10:00", "11:00")
        assert detect_time_block_overlap(new, [existing]) is False

    def test_different_day_no_overlap(self):
        existing = _block(0, "09:00", "10:00")  # Monday
        new = _block(1, "09:00", "10:00")        # Tuesday
        assert detect_time_block_overlap(new, [existing]) is False

    def test_multiple_blocks_one_overlaps(self):
        blocks = [
            _block(0, "08:00", "09:00"),
            _block(0, "11:00", "12:00"),
            _block(0, "14:00", "15:00"),
        ]
        new = _block(0, "10:30", "11:30")
        assert detect_time_block_overlap(new, blocks) is True

    def test_multiple_blocks_none_overlap(self):
        blocks = [
            _block(0, "08:00", "09:00"),
            _block(0, "11:00", "12:00"),
            _block(0, "14:00", "15:00"),
        ]
        new = _block(0, "09:30", "10:30")
        assert detect_time_block_overlap(new, blocks) is False


# ---------------------------------------------------------------------------
# compute_free_slots
# ---------------------------------------------------------------------------

class TestComputeFreeSlots:
    def test_empty_day_returns_full_active_hours(self, config):
        day = date(2024, 1, 1)  # Monday
        slots = compute_free_slots(day, [], [], config)
        assert len(slots) == 1
        assert slots[0].start_time == "08:00"
        assert slots[0].end_time == "20:00"
        assert slots[0].duration_minutes == 720

    def test_single_block_splits_day(self, config):
        day = date(2024, 1, 1)  # Monday (day_of_week=0)
        blocks = [_block(0, "10:00", "11:00")]
        slots = compute_free_slots(day, blocks, [], config)
        assert len(slots) == 2
        assert slots[0].start_time == "08:00"
        assert slots[0].end_time == "10:00"
        assert slots[1].start_time == "11:00"
        assert slots[1].end_time == "20:00"

    def test_block_at_start_of_day(self, config):
        day = date(2024, 1, 1)
        blocks = [_block(0, "08:00", "09:00")]
        slots = compute_free_slots(day, blocks, [], config)
        assert len(slots) == 1
        assert slots[0].start_time == "09:00"
        assert slots[0].end_time == "20:00"

    def test_block_at_end_of_day(self, config):
        day = date(2024, 1, 1)
        blocks = [_block(0, "19:00", "20:00")]
        slots = compute_free_slots(day, blocks, [], config)
        assert len(slots) == 1
        assert slots[0].start_time == "08:00"
        assert slots[0].end_time == "19:00"

    def test_fully_blocked_day_returns_empty(self, config):
        day = date(2024, 1, 1)
        blocks = [_block(0, "08:00", "20:00")]
        slots = compute_free_slots(day, blocks, [], config)
        assert slots == []

    def test_scheduled_task_occupies_slot(self, config):
        day = date(2024, 1, 1)
        entries = [_entry(day, "09:00", "10:00")]
        slots = compute_free_slots(day, [], entries, config)
        assert len(slots) == 2
        assert slots[0].end_time == "09:00"
        assert slots[1].start_time == "10:00"

    def test_adjacent_blocks_merge_correctly(self, config):
        day = date(2024, 1, 1)
        blocks = [
            _block(0, "09:00", "10:00"),
            _block(0, "10:00", "11:00"),
        ]
        slots = compute_free_slots(day, blocks, [], config)
        assert len(slots) == 2
        assert slots[0].end_time == "09:00"
        assert slots[1].start_time == "11:00"

    def test_overlapping_blocks_merge(self, config):
        day = date(2024, 1, 1)
        blocks = [
            _block(0, "09:00", "11:00"),
            _block(0, "10:00", "12:00"),
        ]
        slots = compute_free_slots(day, blocks, [], config)
        assert len(slots) == 2
        assert slots[0].end_time == "09:00"
        assert slots[1].start_time == "12:00"

    def test_block_on_different_day_ignored(self, config):
        day = date(2024, 1, 1)  # Monday
        blocks = [_block(1, "09:00", "10:00")]  # Tuesday
        slots = compute_free_slots(day, blocks, [], config)
        assert len(slots) == 1
        assert slots[0].duration_minutes == 720

    def test_free_slots_cover_full_active_hours(self, config):
        """Union of free slots + occupied must equal active hours."""
        day = date(2024, 1, 1)
        blocks = [_block(0, "10:00", "11:00"), _block(0, "14:00", "15:00")]
        slots = compute_free_slots(day, blocks, [], config)
        total_free = sum(s.duration_minutes for s in slots)
        total_occupied = 60 + 60  # two 1-hour blocks
        assert total_free + total_occupied == 720  # 08:00-20:00 = 720 min

    def test_duration_minutes_correct(self, config):
        day = date(2024, 1, 1)
        blocks = [_block(0, "10:00", "12:00")]
        slots = compute_free_slots(day, blocks, [], config)
        for slot in slots:
            from ai_day_planner.modules.calendar.service import _time_to_minutes
            expected = _time_to_minutes(slot.end_time) - _time_to_minutes(slot.start_time)
            assert slot.duration_minutes == expected

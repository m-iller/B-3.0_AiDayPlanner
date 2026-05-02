"""
Pure domain logic for the Calendar module.

No database access, no side effects. All functions are deterministic.
"""

from __future__ import annotations

from datetime import date, timedelta

from ai_day_planner.config import CalendarConfig
from ai_day_planner.modules.calendar.models import (
    FreeSlot,
    ScheduleEntry,
    TimeBlock,
)


def _time_to_minutes(time_str: str) -> int:
    """Convert 'HH:MM' to total minutes since midnight."""
    h, m = time_str.split(":")
    return int(h) * 60 + int(m)


def _minutes_to_time(minutes: int) -> str:
    """Convert total minutes since midnight to 'HH:MM'."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def detect_time_block_overlap(
    new_block: TimeBlock,
    existing_blocks: list[TimeBlock],
) -> bool:
    """
    Return True if new_block overlaps any block in existing_blocks on the same day.

    Two intervals [a, b) and [c, d) overlap iff a < d and c < b.
    """
    new_start = _time_to_minutes(new_block.start_time)
    new_end = _time_to_minutes(new_block.end_time)

    for block in existing_blocks:
        if block.day_of_week != new_block.day_of_week:
            continue
        existing_start = _time_to_minutes(block.start_time)
        existing_end = _time_to_minutes(block.end_time)
        if new_start < existing_end and existing_start < new_end:
            return True

    return False


def compute_free_slots(
    day: date,
    time_blocks: list[TimeBlock],
    scheduled_tasks: list[ScheduleEntry],
    config: CalendarConfig,
) -> list[FreeSlot]:
    """
    Compute free slots for a given day.

    Free slots are intervals within configured active hours not occupied by
    any TimeBlock or ScheduleEntry on that day.

    Invariants guaranteed:
    - No free slot overlaps any time block or scheduled task.
    - The union of all free slots + time blocks + scheduled tasks covers
      the full active hours with no gaps.

    Args:
        day:             The date to compute free slots for.
        time_blocks:     All time blocks (filtered to this day's day_of_week).
        scheduled_tasks: All schedule entries for this date.
        config:          Calendar config providing active hours.

    Returns:
        Sorted list of FreeSlot objects.
    """
    active_start = _time_to_minutes(config.active_hours_start)
    active_end = _time_to_minutes(config.active_hours_end)

    # Collect all occupied intervals on this day
    occupied: list[tuple[int, int]] = []

    day_of_week = day.weekday()  # 0=Mon … 6=Sun
    for block in time_blocks:
        if block.day_of_week == day_of_week:
            s = _time_to_minutes(block.start_time)
            e = _time_to_minutes(block.end_time)
            occupied.append((s, e))

    for entry in scheduled_tasks:
        if entry.scheduled_date == day:
            s = _time_to_minutes(entry.slot_start)
            e = _time_to_minutes(entry.slot_end)
            occupied.append((s, e))

    # Clip occupied intervals to active hours and sort
    clipped: list[tuple[int, int]] = []
    for s, e in occupied:
        cs = max(s, active_start)
        ce = min(e, active_end)
        if cs < ce:
            clipped.append((cs, ce))

    clipped.sort()

    # Merge overlapping occupied intervals
    merged: list[tuple[int, int]] = []
    for s, e in clipped:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    # Compute gaps (free slots) between occupied intervals
    free_slots: list[FreeSlot] = []
    cursor = active_start

    for occ_start, occ_end in merged:
        if cursor < occ_start:
            free_slots.append(FreeSlot(
                date=day,
                start_time=_minutes_to_time(cursor),
                end_time=_minutes_to_time(occ_start),
                duration_minutes=occ_start - cursor,
            ))
        cursor = max(cursor, occ_end)

    # Trailing free slot after last occupied interval
    if cursor < active_end:
        free_slots.append(FreeSlot(
            date=day,
            start_time=_minutes_to_time(cursor),
            end_time=_minutes_to_time(active_end),
            duration_minutes=active_end - cursor,
        ))

    return free_slots

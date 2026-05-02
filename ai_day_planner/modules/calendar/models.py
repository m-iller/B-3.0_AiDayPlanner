"""
Pydantic models for the Calendar module.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class TimeBlock(BaseModel):
    id: str
    day_of_week: int = Field(ge=0, le=6)  # 0=Mon … 6=Sun
    start_time: str   # "HH:MM"
    end_time: str     # "HH:MM"
    label: str
    is_recurring: bool
    week_number: Optional[int] = None
    year: Optional[int] = None


class TimeBlockCreateRequest(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: str
    end_time: str
    label: str = Field(min_length=1)
    is_recurring: bool = True
    week_number: Optional[int] = None
    year: Optional[int] = None


class FreeSlot(BaseModel):
    date: date
    start_time: str   # "HH:MM"
    end_time: str     # "HH:MM"
    duration_minutes: int


class ScheduleEntry(BaseModel):
    id: str
    task_id: str
    scheduled_date: date
    slot_start: str   # "HH:MM"
    slot_end: str     # "HH:MM"
    is_confirmed: bool


class WeeklyView(BaseModel):
    week_number: int
    year: int
    time_blocks: list[TimeBlock]
    schedule_entries: list[ScheduleEntry]
    free_slots: dict[str, list[FreeSlot]]  # keyed by ISO date string "YYYY-MM-DD"

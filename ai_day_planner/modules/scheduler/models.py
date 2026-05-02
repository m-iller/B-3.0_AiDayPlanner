"""
Pydantic models for the Scheduler module.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel

from ai_day_planner.modules.calendar.models import FreeSlot


class ScheduleDecision(BaseModel):
    task_id: str
    outcome: Literal["assigned", "skipped", "deferred"]
    slot: Optional[FreeSlot] = None
    priority_score: float
    fatigue_score: int
    completion_probability: Optional[float] = None
    reason: str


class ScheduleResult(BaseModel):
    assigned: list[ScheduleDecision]
    skipped: list[ScheduleDecision]
    deferred: list[ScheduleDecision]

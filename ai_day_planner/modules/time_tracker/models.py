"""
Pydantic models for the Time Tracker module.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from ai_day_planner.modules.tasks.models import TaskState


class TrackingAction(str, Enum):
    start = "start"
    stop = "stop"
    interrupt_start = "interrupt_start"
    interrupt_end = "interrupt_end"


class Interruption(BaseModel):
    id: str
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None


class TrackingSession(BaseModel):
    id: str
    task_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    actual_duration: Optional[int] = None   # minutes
    interruptions: list[Interruption] = []

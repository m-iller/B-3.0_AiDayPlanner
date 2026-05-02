"""
Pydantic models for the Probability module.
"""

from __future__ import annotations

from pydantic import BaseModel


class CompletionProbability(BaseModel):
    task_id: str
    slot_start: str       # "HH:MM"
    slot_date: str        # ISO date "YYYY-MM-DD"
    probability: float    # [0.0, 1.0]


class DayAggregate(BaseModel):
    date: str             # ISO date "YYYY-MM-DD"
    aggregate_probability: float   # [0.0, 1.0]
    task_count: int
    is_overloaded: bool   # True when aggregate < daily_overload_threshold

"""
Pydantic models for the Fatigue module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel


class FatigueRecord(BaseModel):
    id: str
    record_date: str          # ISO date "YYYY-MM-DD"
    score: int                # [min_score, max_score]
    updated_at: datetime


class FatigueUpdate(BaseModel):
    date: str                 # ISO date
    delta: float
    cause: Literal["task_completed", "rest", "manual_override"]
    cause_detail: Optional[dict[str, Any]] = None
    override_reason: Optional[str] = None


class FatigueAuditEntry(BaseModel):
    id: str
    record_date: str
    old_score: int
    new_score: int
    cause: str
    cause_detail: Optional[str] = None
    override_reason: Optional[str] = None
    created_at: datetime

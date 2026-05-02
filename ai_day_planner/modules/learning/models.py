"""
Pydantic models for the Learning module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CorrectionCoefficient(BaseModel):
    task_id: str
    coefficient: float
    session_count: int
    updated_at: datetime
    reset_reason: Optional[str] = None

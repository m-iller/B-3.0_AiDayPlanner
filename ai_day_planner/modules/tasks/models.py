"""
Pydantic models for the Task module.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    one_time = "one_time"
    recurring = "recurring"
    no_date = "no_date"


class TaskState(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    interrupted = "interrupted"
    completed = "completed"


class RecurrenceRule(BaseModel):
    interval: int = Field(gt=0)
    unit: Literal["day", "week", "month"]


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    difficulty: int
    urgency: int
    importance: int
    estimated_duration: int = Field(gt=0)
    task_type: TaskType
    dependency_ids: list[str] = []
    recurrence_rule: Optional[RecurrenceRule] = None


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    difficulty: Optional[int] = None
    urgency: Optional[int] = None
    importance: Optional[int] = None
    estimated_duration: Optional[int] = Field(default=None, gt=0)
    task_type: Optional[TaskType] = None
    dependency_ids: Optional[list[str]] = None
    recurrence_rule: Optional[RecurrenceRule] = None


class Task(BaseModel):
    id: str
    title: str
    description: str
    difficulty: int
    urgency: int
    importance: int
    estimated_duration: int
    task_type: TaskType
    state: TaskState
    recurrence_rule: Optional[RecurrenceRule]
    dependency_ids: list[str]
    created_at: datetime
    updated_at: datetime


class TaskQueryFilters(BaseModel):
    task_type: Optional[TaskType] = None
    difficulty_min: Optional[int] = None
    difficulty_max: Optional[int] = None
    urgency_min: Optional[int] = None
    urgency_max: Optional[int] = None
    importance_min: Optional[int] = None
    importance_max: Optional[int] = None
    is_scheduled: Optional[bool] = None


class FieldValidationError(BaseModel):
    field: str
    constraint: str
    received: Any

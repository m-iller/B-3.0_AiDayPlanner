"""
FastAPI router for the Task module.

All responses wrapped in ApiResponse. Events emitted after successful DB writes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from ai_day_planner.event_bus import TASK_CREATED, TASK_DELETED, TASK_UPDATED
from ai_day_planner.modules.shared.models import ApiResponse, ConflictError, DomainValidationError, NotFoundError
from ai_day_planner.modules.tasks.models import (
    Task,
    TaskCreateRequest,
    TaskQueryFilters,
    TaskState,
    TaskType,
    TaskUpdateRequest,
)
from ai_day_planner.modules.tasks.repository import TaskRepository
from ai_day_planner.modules.tasks.service import (
    detect_circular_dependency,
    validate_task_fields,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_repo(request: Request) -> TaskRepository:
    return TaskRepository(request.app.state.db_conn)


@router.post("", response_model=ApiResponse[Task])
def create_task(body: TaskCreateRequest, request: Request):
    repo = _get_repo(request)
    config = request.app.state.config
    logger = request.app.state.logger
    bus = request.app.state.event_bus

    # Domain validation
    errors = validate_task_fields(body, config.task)
    if errors:
        raise DomainValidationError(
            "Task validation failed",
            fields=[e.model_dump() for e in errors],
        )

    # Dependency existence check
    all_tasks = repo.get_all_as_dict()
    for dep_id in body.dependency_ids:
        if dep_id not in all_tasks:
            raise DomainValidationError(
                f"Dependency task not found: {dep_id}",
                fields=[{"field": "dependency_ids", "constraint": "must reference existing tasks", "received": dep_id}],
            )

    # Circular dependency check
    if detect_circular_dependency("__new__", body.dependency_ids, all_tasks):
        raise ConflictError("Adding these dependencies would create a circular dependency")

    now = datetime.now(tz=timezone.utc)
    task = Task(
        id=str(uuid.uuid4()),
        title=body.title,
        description=body.description,
        difficulty=body.difficulty,
        urgency=body.urgency,
        importance=body.importance,
        estimated_duration=body.estimated_duration,
        task_type=body.task_type,
        state=TaskState.pending,
        recurrence_rule=body.recurrence_rule,
        dependency_ids=body.dependency_ids,
        created_at=now,
        updated_at=now,
    )
    created = repo.create(task)
    logger.info("Task created", extra={"task_id": created.id})
    bus.publish(TASK_CREATED, {"task_id": created.id, "task_type": created.task_type.value})
    return ApiResponse.ok(created)


@router.get("/{task_id}", response_model=ApiResponse[Task])
def get_task(task_id: str, request: Request):
    repo = _get_repo(request)
    task = repo.get_by_id(task_id)
    if task is None:
        raise NotFoundError("Task", task_id)
    return ApiResponse.ok(task)


@router.patch("/{task_id}", response_model=ApiResponse[Task])
def update_task(task_id: str, body: TaskUpdateRequest, request: Request):
    repo = _get_repo(request)
    config = request.app.state.config
    bus = request.app.state.event_bus
    logger = request.app.state.logger

    existing = repo.get_by_id(task_id)
    if existing is None:
        raise NotFoundError("Task", task_id)

    updates = body.model_dump(exclude_none=True)
    updated = repo.update(task_id, updates)
    logger.info("Task updated", extra={"task_id": task_id})
    bus.publish(TASK_UPDATED, {"task_id": task_id})
    return ApiResponse.ok(updated)


@router.delete("/{task_id}", response_model=ApiResponse[dict])
def delete_task(task_id: str, request: Request):
    repo = _get_repo(request)
    bus = request.app.state.event_bus
    logger = request.app.state.logger

    existing = repo.get_by_id(task_id)
    if existing is None:
        raise NotFoundError("Task", task_id)

    repo.delete(task_id)
    logger.info("Task deleted", extra={"task_id": task_id})
    bus.publish(TASK_DELETED, {"task_id": task_id})
    return ApiResponse.ok({"deleted": task_id})


@router.get("", response_model=ApiResponse[list[Task]])
def list_tasks(
    request: Request,
    task_type: Optional[TaskType] = Query(default=None),
    difficulty_min: Optional[int] = Query(default=None),
    difficulty_max: Optional[int] = Query(default=None),
    urgency_min: Optional[int] = Query(default=None),
    urgency_max: Optional[int] = Query(default=None),
    importance_min: Optional[int] = Query(default=None),
    importance_max: Optional[int] = Query(default=None),
    is_scheduled: Optional[bool] = Query(default=None),
):
    repo = _get_repo(request)
    filters = TaskQueryFilters(
        task_type=task_type,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        urgency_min=urgency_min,
        urgency_max=urgency_max,
        importance_min=importance_min,
        importance_max=importance_max,
        is_scheduled=is_scheduled,
    )
    tasks = repo.query(filters)
    return ApiResponse.ok(tasks)

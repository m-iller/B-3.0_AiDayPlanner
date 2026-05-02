"""
FastAPI router for the Time Tracker module.

Enforces state machine transitions. Emits task_tracked on session completion.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from ai_day_planner.event_bus import TASK_TRACKED
from ai_day_planner.modules.shared.models import ApiResponse, ConflictError, NotFoundError
from ai_day_planner.modules.tasks.models import TaskState
from ai_day_planner.modules.tasks.repository import TaskRepository
from ai_day_planner.modules.time_tracker.models import TrackingAction, TrackingSession
from ai_day_planner.modules.time_tracker.repository import (
    InterruptionRepository,
    TrackingSessionRepository,
)
from ai_day_planner.modules.time_tracker.service import (
    compute_actual_duration,
    validate_state_transition,
)

router = APIRouter(prefix="/tracking", tags=["tracking"])


def _get_repos(request: Request):
    from ai_day_planner.database import get_connection
    conn = get_connection(request.app.state.db_path)
    return TrackingSessionRepository(conn), InterruptionRepository(conn), TaskRepository(conn)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


@router.post("/start", response_model=ApiResponse[TrackingSession])
def start_tracking(request: Request, task_id: str):
    session_repo, _, task_repo = _get_repos(request)
    logger = request.app.state.logger

    task = task_repo.get_by_id(task_id)
    if task is None:
        raise NotFoundError("Task", task_id)

    if not validate_state_transition(task.state, TrackingAction.start):
        raise ConflictError(
            f"Cannot start tracking: task is in state '{task.state.value}'",
            details={"current_state": task.state.value, "action": "start"},
        )

    task_repo.update(task_id, {"state": TaskState.in_progress})
    session = session_repo.create(task_id, _now())
    logger.info("Tracking started", extra={"task_id": task_id, "session_id": session.id})
    return ApiResponse.ok(session)


@router.post("/stop", response_model=ApiResponse[TrackingSession])
def stop_tracking(request: Request, task_id: str):
    session_repo, intr_repo, task_repo = _get_repos(request)
    bus = request.app.state.event_bus
    logger = request.app.state.logger

    task = task_repo.get_by_id(task_id)
    if task is None:
        raise NotFoundError("Task", task_id)

    if not validate_state_transition(task.state, TrackingAction.stop):
        raise ConflictError(
            f"Cannot stop tracking: task is in state '{task.state.value}'",
            details={"current_state": task.state.value, "action": "stop"},
        )

    # Find the open session
    sessions = session_repo.get_by_task_id(task_id)
    open_session = next((s for s in sessions if s.end_time is None), None)
    if open_session is None:
        raise ConflictError("No open tracking session found for task", details={"task_id": task_id})

    end_time = _now()

    # Auto-close any open interruption
    if task.state == TaskState.interrupted:
        open_intr = intr_repo.get_open_for_session(open_session.id)
        if open_intr:
            intr_repo.close(open_intr.id, end_time)

    # Reload interruptions after potential auto-close
    interruptions = intr_repo.get_for_session(open_session.id)
    actual_duration = compute_actual_duration(open_session.start_time, end_time, interruptions)

    closed = session_repo.close(open_session.id, end_time, actual_duration)
    task_repo.update(task_id, {"state": TaskState.completed})

    logger.info("Tracking stopped", extra={
        "task_id": task_id,
        "session_id": closed.id,
        "actual_duration": actual_duration,
    })
    bus.publish(TASK_TRACKED, {
        "task_id": task_id,
        "session_id": closed.id,
        "actual_duration": actual_duration,
        "estimated_duration": task.estimated_duration,
    })
    return ApiResponse.ok(closed)


@router.post("/interrupt/start", response_model=ApiResponse[dict])
def start_interruption(request: Request, task_id: str):
    session_repo, intr_repo, task_repo = _get_repos(request)
    logger = request.app.state.logger

    task = task_repo.get_by_id(task_id)
    if task is None:
        raise NotFoundError("Task", task_id)

    if not validate_state_transition(task.state, TrackingAction.interrupt_start):
        raise ConflictError(
            f"Cannot start interruption: task is in state '{task.state.value}'",
            details={"current_state": task.state.value},
        )

    sessions = session_repo.get_by_task_id(task_id)
    open_session = next((s for s in sessions if s.end_time is None), None)
    if open_session is None:
        raise ConflictError("No open tracking session found", details={"task_id": task_id})

    intr = intr_repo.create(open_session.id, _now())
    task_repo.update(task_id, {"state": TaskState.interrupted})
    logger.info("Interruption started", extra={"task_id": task_id, "interruption_id": intr.id})
    return ApiResponse.ok({"interruption_id": intr.id, "task_id": task_id})


@router.post("/interrupt/end", response_model=ApiResponse[dict])
def end_interruption(request: Request, task_id: str):
    session_repo, intr_repo, task_repo = _get_repos(request)
    logger = request.app.state.logger

    task = task_repo.get_by_id(task_id)
    if task is None:
        raise NotFoundError("Task", task_id)

    if not validate_state_transition(task.state, TrackingAction.interrupt_end):
        raise ConflictError(
            f"Cannot end interruption: task is in state '{task.state.value}'",
            details={"current_state": task.state.value},
        )

    sessions = session_repo.get_by_task_id(task_id)
    open_session = next((s for s in sessions if s.end_time is None), None)
    if open_session is None:
        raise ConflictError("No open tracking session found", details={"task_id": task_id})

    open_intr = intr_repo.get_open_for_session(open_session.id)
    if open_intr is None:
        raise ConflictError("No open interruption found for session", details={"session_id": open_session.id})

    closed_intr = intr_repo.close(open_intr.id, _now())
    task_repo.update(task_id, {"state": TaskState.in_progress})
    logger.info("Interruption ended", extra={"task_id": task_id, "interruption_id": closed_intr.id})
    return ApiResponse.ok({"interruption_id": closed_intr.id, "task_id": task_id})


@router.get("/{task_id}", response_model=ApiResponse[list[TrackingSession]])
def get_tracking_sessions(task_id: str, request: Request):
    session_repo, _, task_repo = _get_repos(request)

    task = task_repo.get_by_id(task_id)
    if task is None:
        raise NotFoundError("Task", task_id)

    sessions = session_repo.get_by_task_id(task_id)
    return ApiResponse.ok(sessions)

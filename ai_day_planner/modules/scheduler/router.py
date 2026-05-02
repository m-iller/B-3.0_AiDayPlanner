"""
FastAPI router for the Scheduler module.

Orchestrates: fetch tasks/slots/fatigue/coefficients/probabilities →
call pure assign_tasks_to_slots → persist (unless dry_run) → emit event.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from typing import Optional

from fastapi import APIRouter, Query, Request

from ai_day_planner.event_bus import SCHEDULE_UPDATED
from ai_day_planner.modules.calendar.models import ScheduleEntry
from ai_day_planner.modules.calendar.repository import (
    ScheduleEntryRepository,
    TimeBlockRepository,
)
from ai_day_planner.modules.calendar.service import compute_free_slots
from ai_day_planner.modules.fatigue.repository import FatigueRepository
from ai_day_planner.modules.learning.repository import CoefficientRepository
from ai_day_planner.modules.probability.service import compute_completion_probability
from ai_day_planner.modules.scheduler.models import ScheduleResult
from ai_day_planner.modules.scheduler.service import assign_tasks_to_slots
from ai_day_planner.modules.shared.models import ApiResponse, NotFoundError
from ai_day_planner.modules.tasks.models import TaskQueryFilters, TaskState
from ai_day_planner.modules.tasks.repository import TaskRepository

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.post("/run", response_model=ApiResponse[ScheduleResult])
def run_schedule(
    request: Request,
    dry_run: bool = Query(default=False),
    week_number: int = Query(..., ge=1, le=53),
    year: int = Query(..., ge=2000, le=2100),
    schedule_date: Optional[str] = Query(default=None, description="ISO date to schedule for (defaults to today)"),
):
    config = request.app.state.config
    from ai_day_planner.database import get_connection
    conn = get_connection(request.app.state.db_path)
    bus = request.app.state.event_bus
    logger = request.app.state.logger

    target_date = date.fromisoformat(schedule_date) if schedule_date else date.today()
    date_str = target_date.isoformat()

    # Fetch unscheduled tasks
    task_repo = TaskRepository(conn)
    unscheduled = task_repo.query(TaskQueryFilters(is_scheduled=False))
    pending_tasks = [t for t in unscheduled if t.state == TaskState.pending]

    # Fetch free slots for target date
    tb_repo = TimeBlockRepository(conn)
    se_repo = ScheduleEntryRepository(conn)
    time_blocks = tb_repo.get_for_day(target_date.weekday())
    existing_entries = se_repo.get_for_day(target_date)
    free_slots = compute_free_slots(target_date, time_blocks, existing_entries, config.calendar)

    # Fetch fatigue score
    fatigue_repo = FatigueRepository(conn)
    fatigue_record = fatigue_repo.get_or_create_for_date(date_str, config.fatigue.min_score)
    fatigue_score = fatigue_record.score

    # Fetch correction coefficients
    coeff_repo = CoefficientRepository(conn, config.learning.default_correction_coefficient)
    coefficients: dict[str, float] = {}
    for task in pending_tasks:
        coefficients[task.id] = coeff_repo.get_or_default(task.id).coefficient

    # Compute probabilities for each (task, slot) pair
    probabilities: dict[tuple[str, str], float] = {}
    for task in pending_tasks:
        for slot in free_slots:
            slot_key = f"{slot.date.isoformat()} {slot.start_time}"
            h, m = slot.start_time.split(":")
            slot_time = time(int(h), int(m))
            prob = compute_completion_probability(
                fatigue_score=fatigue_score,
                task_difficulty=task.difficulty,
                slot_start=slot_time,
                correction_coefficient=coefficients.get(task.id, 1.0),
                historical_completion_rate=None,
                config=config.probability,
                fatigue_config=config.fatigue,
                task_config=config.task,
            )
            probabilities[(task.id, slot_key)] = prob

    # Run pure scheduling algorithm
    result = assign_tasks_to_slots(
        tasks=pending_tasks,
        free_slots=free_slots,
        fatigue_score=fatigue_score,
        coefficients=coefficients,
        probabilities=probabilities,
        config=config.scheduler,
        fatigue_config=config.fatigue,
        logger=logger,
    )

    # Persist unless dry_run
    if not dry_run:
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        for decision in result.assigned:
            if decision.slot is None:
                continue
            entry = ScheduleEntry(
                id=str(uuid.uuid4()),
                task_id=decision.task_id,
                scheduled_date=decision.slot.date,
                slot_start=decision.slot.start_time,
                slot_end=decision.slot.end_time,
                is_confirmed=False,
            )
            se_repo.create(entry)

        bus.publish(SCHEDULE_UPDATED, {
            "assigned_count": len(result.assigned),
            "skipped_count": len(result.skipped),
            "deferred_count": len(result.deferred),
            "dry_run": False,
        })
        logger.info("Schedule run complete", extra={
            "assigned": len(result.assigned),
            "skipped": len(result.skipped),
            "deferred": len(result.deferred),
            "dry_run": False,
        })
    else:
        logger.info("Schedule dry-run complete", extra={
            "assigned": len(result.assigned),
            "skipped": len(result.skipped),
            "deferred": len(result.deferred),
            "dry_run": True,
        })

    return ApiResponse.ok(result)


@router.post("/confirm/{entry_id}", response_model=ApiResponse[dict])
def confirm_schedule_entry(entry_id: str, request: Request):
    from ai_day_planner.database import get_connection
    conn = get_connection(request.app.state.db_path)
    logger = request.app.state.logger

    se_repo = ScheduleEntryRepository(conn)
    se_repo.confirm(entry_id)
    logger.info("Schedule entry confirmed", extra={"entry_id": entry_id})
    return ApiResponse.ok({"confirmed": entry_id})

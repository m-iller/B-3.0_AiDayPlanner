"""
FastAPI router for the Probability module.
"""

from __future__ import annotations

from datetime import time

from fastapi import APIRouter, Query, Request

from ai_day_planner.modules.calendar.repository import ScheduleEntryRepository
from ai_day_planner.modules.fatigue.repository import FatigueRepository
from ai_day_planner.modules.learning.repository import CoefficientRepository
from ai_day_planner.modules.probability.models import CompletionProbability, DayAggregate
from ai_day_planner.modules.probability.service import (
    compute_completion_probability,
    compute_day_aggregate_probability,
)
from ai_day_planner.modules.shared.models import ApiResponse
from ai_day_planner.modules.tasks.repository import TaskRepository

router = APIRouter(prefix="/probability", tags=["probability"])


@router.get("/task", response_model=ApiResponse[CompletionProbability])
def get_task_probability(
    request: Request,
    task_id: str = Query(...),
    slot_date: str = Query(..., description="ISO date YYYY-MM-DD"),
    slot_start: str = Query(..., description="HH:MM"),
):
    config = request.app.state.config
    conn = request.app.state.db_conn

    task_repo = TaskRepository(conn)
    fatigue_repo = FatigueRepository(conn)
    coeff_repo = CoefficientRepository(conn, config.learning.default_correction_coefficient)

    task = task_repo.get_by_id(task_id)
    if task is None:
        from ai_day_planner.modules.shared.models import NotFoundError
        raise NotFoundError("Task", task_id)

    fatigue_record = fatigue_repo.get_or_create_for_date(slot_date, config.fatigue.min_score)
    coeff = coeff_repo.get_or_default(task_id)

    h, m = slot_start.split(":")
    slot_time = time(int(h), int(m))

    prob = compute_completion_probability(
        fatigue_score=fatigue_record.score,
        task_difficulty=task.difficulty,
        slot_start=slot_time,
        correction_coefficient=coeff.coefficient,
        historical_completion_rate=None,
        config=config.probability,
        fatigue_config=config.fatigue,
        task_config=config.task,
    )

    return ApiResponse.ok(CompletionProbability(
        task_id=task_id,
        slot_start=slot_start,
        slot_date=slot_date,
        probability=prob,
    ))


@router.get("/day/{record_date}", response_model=ApiResponse[DayAggregate])
def get_day_aggregate(record_date: str, request: Request):
    config = request.app.state.config
    conn = request.app.state.db_conn

    from datetime import date as date_type
    day = date_type.fromisoformat(record_date)

    se_repo = ScheduleEntryRepository(conn)
    task_repo = TaskRepository(conn)
    fatigue_repo = FatigueRepository(conn)
    coeff_repo = CoefficientRepository(conn, config.learning.default_correction_coefficient)

    entries = se_repo.get_for_day(day)
    fatigue_record = fatigue_repo.get_or_create_for_date(record_date, config.fatigue.min_score)

    probs: list[float] = []
    for entry in entries:
        task = task_repo.get_by_id(entry.task_id)
        if task is None:
            continue
        coeff = coeff_repo.get_or_default(entry.task_id)
        h, m = entry.slot_start.split(":")
        slot_time = time(int(h), int(m))
        p = compute_completion_probability(
            fatigue_score=fatigue_record.score,
            task_difficulty=task.difficulty,
            slot_start=slot_time,
            correction_coefficient=coeff.coefficient,
            historical_completion_rate=None,
            config=config.probability,
            fatigue_config=config.fatigue,
            task_config=config.task,
        )
        probs.append(p)

    aggregate = compute_day_aggregate_probability(probs, config.probability)
    is_overloaded = aggregate < config.scheduler.daily_overload_threshold

    return ApiResponse.ok(DayAggregate(
        date=record_date,
        aggregate_probability=aggregate,
        task_count=len(probs),
        is_overloaded=is_overloaded,
    ))

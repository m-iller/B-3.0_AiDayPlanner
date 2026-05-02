"""
FastAPI router for the Calendar module.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query, Request

from ai_day_planner.event_bus import TIME_BLOCK_DELETED
from ai_day_planner.modules.calendar.models import (
    TimeBlock,
    TimeBlockCreateRequest,
    WeeklyView,
)
from ai_day_planner.modules.calendar.repository import (
    ScheduleEntryRepository,
    TimeBlockRepository,
)
from ai_day_planner.modules.calendar.service import (
    compute_free_slots,
    detect_time_block_overlap,
)
from ai_day_planner.modules.shared.models import ApiResponse, ConflictError, NotFoundError

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _get_repos(request: Request):
    from ai_day_planner.database import get_connection
    conn = get_connection(request.app.state.db_path)
    return TimeBlockRepository(conn), ScheduleEntryRepository(conn)


@router.post("/blocks", response_model=ApiResponse[TimeBlock])
def create_time_block(body: TimeBlockCreateRequest, request: Request):
    tb_repo, _ = _get_repos(request)
    logger = request.app.state.logger

    existing = tb_repo.get_for_day(body.day_of_week)
    new_block = TimeBlock(
        id=str(uuid.uuid4()),
        day_of_week=body.day_of_week,
        start_time=body.start_time,
        end_time=body.end_time,
        label=body.label,
        is_recurring=body.is_recurring,
        week_number=body.week_number,
        year=body.year,
    )

    if detect_time_block_overlap(new_block, existing):
        raise ConflictError(
            f"Time block overlaps existing block on day {body.day_of_week}",
            details={"day_of_week": body.day_of_week, "start": body.start_time, "end": body.end_time},
        )

    created = tb_repo.create(new_block)
    logger.info("Time block created", extra={"block_id": created.id})
    return ApiResponse.ok(created)


@router.get("/blocks/{block_id}", response_model=ApiResponse[TimeBlock])
def get_time_block(block_id: str, request: Request):
    tb_repo, _ = _get_repos(request)
    block = tb_repo.get_by_id(block_id)
    if block is None:
        raise NotFoundError("TimeBlock", block_id)
    return ApiResponse.ok(block)


@router.delete("/blocks/{block_id}", response_model=ApiResponse[dict])
def delete_time_block(block_id: str, request: Request):
    tb_repo, _ = _get_repos(request)
    bus = request.app.state.event_bus
    logger = request.app.state.logger

    block = tb_repo.get_by_id(block_id)
    if block is None:
        raise NotFoundError("TimeBlock", block_id)

    tb_repo.delete(block_id)
    logger.info("Time block deleted", extra={"block_id": block_id})
    bus.publish(TIME_BLOCK_DELETED, {"block_id": block_id, "day_of_week": block.day_of_week})
    return ApiResponse.ok({"deleted": block_id})


@router.get("/week", response_model=ApiResponse[WeeklyView])
def get_weekly_view(
    request: Request,
    week_number: int = Query(..., ge=1, le=53),
    year: int = Query(..., ge=2000, le=2100),
):
    tb_repo, se_repo = _get_repos(request)
    config = request.app.state.config

    time_blocks = tb_repo.get_for_week(week_number, year)
    schedule_entries = se_repo.get_for_week(week_number, year)

    # Compute free slots per day
    jan4 = date(year, 1, 4)
    week_start = jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=week_number - 1)
    free_slots_by_day: dict[str, list] = {}

    for i in range(7):
        day = week_start + timedelta(days=i)
        day_entries = [e for e in schedule_entries if e.scheduled_date == day]
        slots = compute_free_slots(day, time_blocks, day_entries, config.calendar)
        free_slots_by_day[day.isoformat()] = slots

    return ApiResponse.ok(WeeklyView(
        week_number=week_number,
        year=year,
        time_blocks=time_blocks,
        schedule_entries=schedule_entries,
        free_slots=free_slots_by_day,
    ))

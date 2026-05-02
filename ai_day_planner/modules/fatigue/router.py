"""
FastAPI router for the Fatigue module.
"""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Request

from ai_day_planner.event_bus import FATIGUE_UPDATED
from ai_day_planner.modules.fatigue.models import FatigueAuditEntry, FatigueRecord
from ai_day_planner.modules.fatigue.repository import FatigueRepository
from ai_day_planner.modules.fatigue.service import apply_fatigue_delta
from ai_day_planner.modules.shared.models import ApiResponse, NotFoundError

router = APIRouter(prefix="/fatigue", tags=["fatigue"])


class FatigueOverrideRequest(BaseModel):
    date: str          # ISO date "YYYY-MM-DD"
    new_score: int
    reason: str


def _get_repo(request: Request) -> FatigueRepository:
    return FatigueRepository(request.app.state.db_conn)


@router.get("/{record_date}", response_model=ApiResponse[FatigueRecord])
def get_fatigue(record_date: str, request: Request):
    repo = _get_repo(request)
    config = request.app.state.config

    record = repo.get_or_create_for_date(record_date, config.fatigue.min_score)
    return ApiResponse.ok(record)


@router.post("/override", response_model=ApiResponse[FatigueRecord])
def override_fatigue(body: FatigueOverrideRequest, request: Request):
    repo = _get_repo(request)
    config = request.app.state.config
    bus = request.app.state.event_bus
    logger = request.app.state.logger

    # Ensure record exists
    existing = repo.get_or_create_for_date(body.date, config.fatigue.min_score)
    old_score = existing.score

    # Clamp new score to configured range
    new_score = max(config.fatigue.min_score, min(config.fatigue.max_score, body.new_score))

    updated = repo.update_score(
        body.date,
        new_score,
        cause="manual_override",
        override_reason=body.reason,
    )
    logger.info(
        "Fatigue score overridden",
        extra={"date": body.date, "old_score": old_score, "new_score": new_score, "reason": body.reason},
    )
    bus.publish(FATIGUE_UPDATED, {
        "date": body.date,
        "old_score": old_score,
        "new_score": new_score,
        "cause": "manual_override",
    })
    return ApiResponse.ok(updated)

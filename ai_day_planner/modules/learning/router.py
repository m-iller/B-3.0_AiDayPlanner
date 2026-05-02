"""
FastAPI router for the Learning module.
"""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Request

from ai_day_planner.event_bus import COEFFICIENT_UPDATED
from ai_day_planner.modules.learning.models import CorrectionCoefficient
from ai_day_planner.modules.learning.repository import CoefficientRepository
from ai_day_planner.modules.shared.models import ApiResponse

router = APIRouter(prefix="/learning", tags=["learning"])


class ResetRequest(BaseModel):
    reason: str


def _get_repo(request: Request) -> CoefficientRepository:
    config = request.app.state.config
    return CoefficientRepository(
        request.app.state.db_conn,
        default_coefficient=config.learning.default_correction_coefficient,
    )


@router.get("/{task_id}", response_model=ApiResponse[CorrectionCoefficient])
def get_coefficient(task_id: str, request: Request):
    repo = _get_repo(request)
    coeff = repo.get_or_default(task_id)
    return ApiResponse.ok(coeff)


@router.post("/{task_id}/reset", response_model=ApiResponse[CorrectionCoefficient])
def reset_coefficient(task_id: str, body: ResetRequest, request: Request):
    repo = _get_repo(request)
    bus = request.app.state.event_bus
    logger = request.app.state.logger

    old = repo.get_or_default(task_id)
    reset = repo.reset(task_id, body.reason)

    logger.info("Coefficient reset", extra={"task_id": task_id, "reason": body.reason})
    bus.publish(COEFFICIENT_UPDATED, {
        "task_id": task_id,
        "old_value": old.coefficient,
        "new_value": reset.coefficient,
        "reason": "reset",
    })
    return ApiResponse.ok(reset)

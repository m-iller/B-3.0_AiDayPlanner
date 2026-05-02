"""
FastAPI application factory for AI Day Planner.

create_app(config_path) → FastAPI:
  - Loads config (fail-fast)
  - Initialises DB migrations
  - Creates EventBus singleton and registers cross-module event handlers
  - Registers all routers under /api/v1/
  - Registers exception handlers
  - Logs every request with method, path, response status
"""

from __future__ import annotations

import dataclasses
import logging
import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ai_day_planner.config import AppConfig, load_config
from ai_day_planner.database import get_connection, run_migrations
from ai_day_planner.event_bus import (
    COEFFICIENT_UPDATED,
    FATIGUE_UPDATED,
    TASK_TRACKED,
    EventBus,
)
from ai_day_planner.logger import configure_logging, get_logger
from ai_day_planner.modules.calendar.router import router as calendar_router
from ai_day_planner.modules.fatigue.repository import FatigueRepository
from ai_day_planner.modules.fatigue.service import (
    apply_fatigue_delta,
    compute_fatigue_increase,
)
from ai_day_planner.modules.learning.repository import CoefficientRepository
from ai_day_planner.modules.learning.service import (
    compute_duration_ratio,
    compute_ema_coefficient,
)
from ai_day_planner.modules.probability.router import router as probability_router
from ai_day_planner.modules.scheduler.router import router as scheduler_router
from ai_day_planner.modules.shared.models import (
    ApiError,
    ApiResponse,
    ConflictError,
    DomainValidationError,
    NotFoundError,
)
from ai_day_planner.modules.tasks.repository import TaskRepository
from ai_day_planner.modules.tasks.router import router as tasks_router
from ai_day_planner.modules.fatigue.router import router as fatigue_router
from ai_day_planner.modules.learning.router import router as learning_router
from ai_day_planner.modules.time_tracker.router import router as tracking_router


# ---------------------------------------------------------------------------
# Event handlers (cross-module wiring via event bus)
# ---------------------------------------------------------------------------

def _make_task_tracked_handler(app: FastAPI):
    """
    On TASK_TRACKED: update fatigue score and learning coefficient.
    """
    def handler(payload: dict) -> None:
        config: AppConfig = app.state.config
        conn = app.state.db_conn
        bus: EventBus = app.state.event_bus
        logger: logging.Logger = app.state.logger

        task_id: str = payload["task_id"]
        actual_duration: int = payload["actual_duration"]
        estimated_duration: int = payload["estimated_duration"]

        # --- Fatigue update ---
        from datetime import date
        today = date.today().isoformat()
        fatigue_repo = FatigueRepository(conn)
        record = fatigue_repo.get_or_create_for_date(today, config.fatigue.min_score)
        old_score = record.score

        task_repo = TaskRepository(conn)
        task = task_repo.get_by_id(task_id)
        difficulty = task.difficulty if task else 5

        delta = compute_fatigue_increase(difficulty, actual_duration, config.fatigue)
        new_score = apply_fatigue_delta(old_score, delta, config.fatigue)
        fatigue_repo.update_score(
            today, new_score, cause="task_completed",
            cause_detail={"task_id": task_id, "actual_duration": actual_duration},
        )
        bus.publish(FATIGUE_UPDATED, {
            "date": today,
            "old_score": old_score,
            "new_score": new_score,
            "cause": "task_completed",
        })
        logger.info("Fatigue updated after task completion", extra={
            "task_id": task_id, "old_score": old_score, "new_score": new_score,
        })

        # --- Learning coefficient update ---
        if estimated_duration > 0:
            coeff_repo = CoefficientRepository(conn, config.learning.default_correction_coefficient)
            current = coeff_repo.get_or_default(task_id)
            ratio = compute_duration_ratio(actual_duration, estimated_duration)
            new_coeff = compute_ema_coefficient(
                current.coefficient, ratio, config.learning.ema_smoothing_factor
            )
            updated = coeff_repo.upsert(task_id, new_coeff)
            bus.publish(COEFFICIENT_UPDATED, {
                "task_id": task_id,
                "old_value": current.coefficient,
                "new_value": new_coeff,
            })
            logger.info("Coefficient updated after task completion", extra={
                "task_id": task_id,
                "old_coefficient": current.coefficient,
                "new_coefficient": new_coeff,
            })

    return handler


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

def _make_exception_handlers(logger: logging.Logger):
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ApiResponse.fail("NOT_FOUND", str(exc)).model_dump(),
        )

    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=ApiResponse.fail("CONFLICT", str(exc), exc.details).model_dump(),
        )

    async def validation_handler(request: Request, exc: DomainValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ApiResponse.fail(
                "VALIDATION_ERROR",
                str(exc),
                {"fields": exc.fields},
            ).model_dump(),
        )

    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled exception",
            extra={
                "path": request.url.path,
                "method": request.method,
                "exception": repr(exc),
                "traceback": traceback.format_exc(),
            },
        )
        return JSONResponse(
            status_code=500,
            content=ApiResponse.fail("INTERNAL_ERROR", "An internal error occurred").model_dump(),
        )

    return not_found_handler, conflict_handler, validation_handler, internal_error_handler


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

def _add_request_logging(app: FastAPI, logger: logging.Logger) -> None:
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        response = await call_next(request)
        logger.info(
            "HTTP request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
            },
        )
        return response


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(config_path: Path | str = "config/default.toml") -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        config_path: Path to the TOML configuration file.

    Returns:
        Configured FastAPI application.

    Raises:
        ConfigurationError: If config is missing or invalid (fail-fast).
    """
    config = load_config(Path(config_path))
    configure_logging(config.logging.level)
    logger = get_logger("ai_day_planner.main", level=config.logging.level)

    db_conn = get_connection(":memory:")  # override via env/config for production
    run_migrations(db_conn)

    bus = EventBus(logger=get_logger("ai_day_planner.event_bus", level=config.logging.level))

    app = FastAPI(
        title="AI Day Planner",
        version="1.0.0",
        description="Modular monolithic day planner with predictive workload and fatigue modeling.",
    )

    # Store shared state
    app.state.config = config
    app.state.db_conn = db_conn
    app.state.event_bus = bus
    app.state.logger = logger

    # Register cross-module event handlers
    bus.subscribe(TASK_TRACKED, _make_task_tracked_handler(app))

    # Register routers under /api/v1/
    prefix = "/api/v1"
    app.include_router(tasks_router, prefix=prefix)
    app.include_router(calendar_router, prefix=prefix)
    app.include_router(fatigue_router, prefix=prefix)
    app.include_router(learning_router, prefix=prefix)
    app.include_router(probability_router, prefix=prefix)
    app.include_router(scheduler_router, prefix=prefix)
    app.include_router(tracking_router, prefix=prefix)

    # Config read-only endpoint
    @app.get(f"{prefix}/config", tags=["config"])
    def get_config():
        return ApiResponse.ok(dataclasses.asdict(config))

    # Exception handlers
    nf, cf, vf, ie = _make_exception_handlers(logger)
    app.add_exception_handler(NotFoundError, nf)
    app.add_exception_handler(ConflictError, cf)
    app.add_exception_handler(DomainValidationError, vf)
    app.add_exception_handler(Exception, ie)

    # Request logging middleware
    _add_request_logging(app, logger)

    logger.info("AI Day Planner started", extra={"config_path": str(config_path)})
    return app

"""
Unit tests for ai_day_planner/modules/scheduler/service.py

Covers: compute_priority_score, apply_fatigue_penalty, assign_tasks_to_slots.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from ai_day_planner.config import FatigueConfig, SchedulerConfig
from ai_day_planner.modules.calendar.models import FreeSlot
from ai_day_planner.modules.scheduler.service import (
    apply_fatigue_penalty,
    assign_tasks_to_slots,
    compute_priority_score,
)
from ai_day_planner.modules.tasks.models import Task, TaskState, TaskType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sched_config() -> SchedulerConfig:
    return SchedulerConfig(
        weight_difficulty=1.0,
        weight_urgency=1.5,
        weight_importance=1.2,
        weight_fatigue=0.8,
        min_completion_probability=0.4,
        daily_overload_threshold=0.5,
    )


@pytest.fixture()
def fatigue_config() -> FatigueConfig:
    return FatigueConfig(
        min_score=1, max_score=100, high_threshold=75,
        increase_difficulty_weight=0.5, increase_duration_weight=0.05,
        recovery_rate_per_minute=0.1, high_fatigue_penalty=0.2,
    )


def _task(
    task_id: str = "t1",
    difficulty: int = 5,
    urgency: int = 5,
    importance: int = 5,
    estimated_duration: int = 60,
    dependency_ids: list[str] | None = None,
) -> Task:
    now = datetime.now(tz=timezone.utc)
    return Task(
        id=task_id,
        title="Task",
        description="",
        difficulty=difficulty,
        urgency=urgency,
        importance=importance,
        estimated_duration=estimated_duration,
        task_type=TaskType.one_time,
        state=TaskState.pending,
        recurrence_rule=None,
        dependency_ids=dependency_ids or [],
        created_at=now,
        updated_at=now,
    )


def _slot(
    day: date | None = None,
    start: str = "09:00",
    end: str = "11:00",
) -> FreeSlot:
    d = day or date(2024, 1, 1)
    h_s, m_s = start.split(":")
    h_e, m_e = end.split(":")
    duration = (int(h_e) * 60 + int(m_e)) - (int(h_s) * 60 + int(m_s))
    return FreeSlot(date=d, start_time=start, end_time=end, duration_minutes=duration)


# ---------------------------------------------------------------------------
# compute_priority_score
# ---------------------------------------------------------------------------

class TestComputePriorityScore:
    def test_formula_correctness(self, sched_config):
        task = _task(difficulty=5, urgency=7, importance=8)
        score = compute_priority_score(task, 30, sched_config)
        expected = 1.0 * 5 + 1.5 * 7 + 1.2 * 8 - 0.8 * 30
        assert abs(score - expected) < 1e-9

    def test_higher_urgency_higher_score(self, sched_config):
        low = compute_priority_score(_task(urgency=2), 20, sched_config)
        high = compute_priority_score(_task(urgency=9), 20, sched_config)
        assert high > low

    def test_higher_fatigue_lower_score(self, sched_config):
        low_f = compute_priority_score(_task(), 10, sched_config)
        high_f = compute_priority_score(_task(), 90, sched_config)
        assert low_f > high_f


# ---------------------------------------------------------------------------
# apply_fatigue_penalty
# ---------------------------------------------------------------------------

class TestApplyFatiguePenalty:
    def test_no_penalty_below_threshold(self, sched_config, fatigue_config):
        # fatigue 50 < threshold 75 — no penalty
        result = apply_fatigue_penalty(100.0, 50, 60, sched_config, fatigue_config)
        assert result == 100.0

    def test_penalty_above_threshold_high_difficulty(self, sched_config, fatigue_config):
        # fatigue 80 > 75, difficulty 60 > midpoint 50.5
        result = apply_fatigue_penalty(100.0, 80, 60, sched_config, fatigue_config)
        assert result < 100.0


# ---------------------------------------------------------------------------
# assign_tasks_to_slots
# ---------------------------------------------------------------------------

class TestAssignTasksToSlots:
    def test_single_task_assigned_to_slot(self, sched_config, fatigue_config):
        tasks = [_task("t1", estimated_duration=60)]
        slots = [_slot(start="09:00", end="11:00")]
        result = assign_tasks_to_slots(
            tasks, slots, 20, {}, {("t1", "2024-01-01 09:00"): 0.8},
            sched_config, fatigue_config,
        )
        assert len(result.assigned) == 1
        assert result.assigned[0].task_id == "t1"

    def test_task_deferred_when_no_slots(self, sched_config, fatigue_config):
        tasks = [_task("t1", estimated_duration=60)]
        result = assign_tasks_to_slots(
            tasks, [], 20, {}, {}, sched_config, fatigue_config,
        )
        assert len(result.deferred) == 1

    def test_task_skipped_when_probability_below_threshold(self, sched_config, fatigue_config):
        tasks = [_task("t1", estimated_duration=60)]
        slots = [_slot(start="09:00", end="11:00")]
        # probability below min_completion_probability (0.4)
        result = assign_tasks_to_slots(
            tasks, slots, 20, {}, {("t1", "2024-01-01 09:00"): 0.1},
            sched_config, fatigue_config,
        )
        assert len(result.skipped) == 1

    def test_slot_too_short_causes_deferral(self, sched_config, fatigue_config):
        tasks = [_task("t1", estimated_duration=120)]
        slots = [_slot(start="09:00", end="09:30")]  # only 30 min
        result = assign_tasks_to_slots(
            tasks, slots, 20, {}, {}, sched_config, fatigue_config,
        )
        assert len(result.deferred) == 1

    def test_higher_priority_task_assigned_first(self, sched_config, fatigue_config):
        # t_high has higher urgency → higher priority
        t_low = _task("t_low", urgency=2, estimated_duration=60)
        t_high = _task("t_high", urgency=9, estimated_duration=60)
        slots = [_slot(start="09:00", end="10:00")]  # only one slot
        probs = {
            ("t_low", "2024-01-01 09:00"): 0.8,
            ("t_high", "2024-01-01 09:00"): 0.8,
        }
        result = assign_tasks_to_slots(
            [t_low, t_high], slots, 20, {}, probs, sched_config, fatigue_config,
        )
        assert len(result.assigned) == 1
        assert result.assigned[0].task_id == "t_high"

    def test_correction_coefficient_affects_slot_fit(self, sched_config, fatigue_config):
        # task needs 60 min, but correction=2.0 means effective=120 min
        tasks = [_task("t1", estimated_duration=60)]
        slots = [_slot(start="09:00", end="10:00")]  # 60 min slot
        result = assign_tasks_to_slots(
            tasks, slots, 20, {"t1": 2.0}, {}, sched_config, fatigue_config,
        )
        # Slot is too short after correction — deferred
        assert len(result.deferred) == 1

    def test_completed_tasks_skipped(self, sched_config, fatigue_config):
        now = datetime.now(tz=timezone.utc)
        completed = Task(
            id="t_done", title="Done", description="",
            difficulty=5, urgency=5, importance=5, estimated_duration=30,
            task_type=TaskType.one_time, state=TaskState.completed,
            recurrence_rule=None, dependency_ids=[],
            created_at=now, updated_at=now,
        )
        slots = [_slot()]
        result = assign_tasks_to_slots(
            [completed], slots, 20, {}, {}, sched_config, fatigue_config,
        )
        assert len(result.assigned) == 0
        assert len(result.deferred) == 0
        assert len(result.skipped) == 0

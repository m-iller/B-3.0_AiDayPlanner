"""
Unit tests for ai_day_planner/modules/tasks/service.py

Covers: validate_task_fields, detect_circular_dependency, compute_priority_score.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ai_day_planner.config import SchedulerConfig, TaskConfig
from ai_day_planner.modules.tasks.models import (
    RecurrenceRule,
    Task,
    TaskCreateRequest,
    TaskState,
    TaskType,
)
from ai_day_planner.modules.tasks.service import (
    compute_priority_score,
    detect_circular_dependency,
    validate_task_fields,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def task_config() -> TaskConfig:
    return TaskConfig(
        difficulty_min=1, difficulty_max=10,
        urgency_min=1, urgency_max=10,
        importance_min=1, importance_max=10,
    )


@pytest.fixture()
def scheduler_config() -> SchedulerConfig:
    return SchedulerConfig(
        weight_difficulty=1.0,
        weight_urgency=1.5,
        weight_importance=1.2,
        weight_fatigue=0.8,
        min_completion_probability=0.4,
        daily_overload_threshold=0.5,
    )


def _make_task(
    task_id: str = "t1",
    difficulty: int = 5,
    urgency: int = 5,
    importance: int = 5,
    task_type: TaskType = TaskType.one_time,
    dependency_ids: list[str] | None = None,
) -> Task:
    return Task(
        id=task_id,
        title="Test Task",
        description="",
        difficulty=difficulty,
        urgency=urgency,
        importance=importance,
        estimated_duration=30,
        task_type=task_type,
        state=TaskState.pending,
        recurrence_rule=None,
        dependency_ids=dependency_ids or [],
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )


def _make_request(
    difficulty: int = 5,
    urgency: int = 5,
    importance: int = 5,
    estimated_duration: int = 30,
    task_type: TaskType = TaskType.one_time,
    title: str = "Valid Task",
    recurrence_rule: RecurrenceRule | None = None,
) -> TaskCreateRequest:
    return TaskCreateRequest(
        title=title,
        difficulty=difficulty,
        urgency=urgency,
        importance=importance,
        estimated_duration=estimated_duration,
        task_type=task_type,
        recurrence_rule=recurrence_rule,
    )


# ---------------------------------------------------------------------------
# validate_task_fields
# ---------------------------------------------------------------------------

class TestValidateTaskFields:
    def test_valid_request_returns_empty_list(self, task_config):
        req = _make_request()
        assert validate_task_fields(req, task_config) == []

    def test_difficulty_below_min_returns_error(self, task_config):
        req = _make_request(difficulty=0)
        errors = validate_task_fields(req, task_config)
        assert any(e.field == "difficulty" for e in errors)

    def test_difficulty_above_max_returns_error(self, task_config):
        req = _make_request(difficulty=11)
        errors = validate_task_fields(req, task_config)
        assert any(e.field == "difficulty" for e in errors)

    def test_urgency_out_of_range_returns_error(self, task_config):
        req = _make_request(urgency=0)
        errors = validate_task_fields(req, task_config)
        assert any(e.field == "urgency" for e in errors)

    def test_importance_out_of_range_returns_error(self, task_config):
        req = _make_request(importance=99)
        errors = validate_task_fields(req, task_config)
        assert any(e.field == "importance" for e in errors)

    def test_multiple_errors_returned_together(self, task_config):
        req = _make_request(difficulty=0, urgency=0, importance=0)
        errors = validate_task_fields(req, task_config)
        fields = {e.field for e in errors}
        assert "difficulty" in fields
        assert "urgency" in fields
        assert "importance" in fields

    def test_recurring_without_recurrence_rule_returns_error(self, task_config):
        req = _make_request(task_type=TaskType.recurring, recurrence_rule=None)
        errors = validate_task_fields(req, task_config)
        assert any(e.field == "recurrence_rule" for e in errors)

    def test_recurring_with_recurrence_rule_is_valid(self, task_config):
        req = _make_request(
            task_type=TaskType.recurring,
            recurrence_rule=RecurrenceRule(interval=1, unit="week"),
        )
        errors = validate_task_fields(req, task_config)
        assert not any(e.field == "recurrence_rule" for e in errors)

    def test_boundary_values_are_valid(self, task_config):
        req = _make_request(difficulty=1, urgency=1, importance=1)
        assert validate_task_fields(req, task_config) == []
        req2 = _make_request(difficulty=10, urgency=10, importance=10)
        assert validate_task_fields(req2, task_config) == []

    def test_error_contains_received_value(self, task_config):
        req = _make_request(difficulty=99)
        errors = validate_task_fields(req, task_config)
        diff_error = next(e for e in errors if e.field == "difficulty")
        assert diff_error.received == 99


# ---------------------------------------------------------------------------
# detect_circular_dependency
# ---------------------------------------------------------------------------

class TestDetectCircularDependency:
    def test_no_deps_returns_false(self):
        tasks = {"t1": _make_task("t1")}
        assert detect_circular_dependency("t1", [], tasks) is False

    def test_no_cycle_returns_false(self):
        # t2 depends on t1; adding t1 -> t2 would be a cycle, but here we add t3 -> t1
        tasks = {
            "t1": _make_task("t1"),
            "t2": _make_task("t2", dependency_ids=["t1"]),
            "t3": _make_task("t3"),
        }
        assert detect_circular_dependency("t3", ["t1"], tasks) is False

    def test_direct_cycle_returns_true(self):
        # t1 depends on t2; adding t2 -> t1 creates a cycle
        tasks = {
            "t1": _make_task("t1", dependency_ids=["t2"]),
            "t2": _make_task("t2"),
        }
        assert detect_circular_dependency("t2", ["t1"], tasks) is True

    def test_transitive_cycle_returns_true(self):
        # t1 -> t2 -> t3; adding t3 -> t1 creates a cycle
        tasks = {
            "t1": _make_task("t1", dependency_ids=["t2"]),
            "t2": _make_task("t2", dependency_ids=["t3"]),
            "t3": _make_task("t3"),
        }
        assert detect_circular_dependency("t3", ["t1"], tasks) is True

    def test_long_chain_cycle_returns_true(self):
        # t1->t2->t3->t4->t5; adding t5->t1 creates cycle
        tasks = {
            "t1": _make_task("t1", dependency_ids=["t2"]),
            "t2": _make_task("t2", dependency_ids=["t3"]),
            "t3": _make_task("t3", dependency_ids=["t4"]),
            "t4": _make_task("t4", dependency_ids=["t5"]),
            "t5": _make_task("t5"),
        }
        assert detect_circular_dependency("t5", ["t1"], tasks) is True

    def test_self_dependency_returns_true(self):
        tasks = {"t1": _make_task("t1")}
        assert detect_circular_dependency("t1", ["t1"], tasks) is True

    def test_unrelated_tasks_no_cycle(self):
        tasks = {
            "t1": _make_task("t1"),
            "t2": _make_task("t2"),
            "t3": _make_task("t3"),
        }
        assert detect_circular_dependency("t1", ["t2"], tasks) is False


# ---------------------------------------------------------------------------
# compute_priority_score
# ---------------------------------------------------------------------------

class TestComputePriorityScore:
    def test_formula_correctness(self, scheduler_config):
        task = _make_task(difficulty=5, urgency=7, importance=8)
        fatigue = 30
        score = compute_priority_score(task, fatigue, scheduler_config)
        expected = (
            1.0 * 5 + 1.5 * 7 + 1.2 * 8 - 0.8 * 30
        )
        assert abs(score - expected) < 1e-9

    def test_higher_urgency_increases_score(self, scheduler_config):
        task_low = _make_task(urgency=2)
        task_high = _make_task(urgency=9)
        fatigue = 20
        assert compute_priority_score(task_high, fatigue, scheduler_config) > \
               compute_priority_score(task_low, fatigue, scheduler_config)

    def test_higher_fatigue_decreases_score(self, scheduler_config):
        task = _make_task()
        score_low_fatigue = compute_priority_score(task, 10, scheduler_config)
        score_high_fatigue = compute_priority_score(task, 90, scheduler_config)
        assert score_low_fatigue > score_high_fatigue

    def test_higher_difficulty_increases_score(self, scheduler_config):
        task_easy = _make_task(difficulty=1)
        task_hard = _make_task(difficulty=10)
        fatigue = 20
        assert compute_priority_score(task_hard, fatigue, scheduler_config) > \
               compute_priority_score(task_easy, fatigue, scheduler_config)

    def test_returns_float(self, scheduler_config):
        task = _make_task()
        score = compute_priority_score(task, 50, scheduler_config)
        assert isinstance(score, float)

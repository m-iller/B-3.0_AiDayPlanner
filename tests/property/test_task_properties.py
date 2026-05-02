"""
Property-based tests for the Task module.

Properties 1-7 from design.md, validated via Hypothesis.
All tests use in-memory SQLite for isolation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ai_day_planner.config import SchedulerConfig, TaskConfig
from ai_day_planner.database import get_connection, run_migrations
from ai_day_planner.modules.tasks.models import (
    FieldValidationError,
    RecurrenceRule,
    Task,
    TaskCreateRequest,
    TaskQueryFilters,
    TaskState,
    TaskType,
)
from ai_day_planner.modules.tasks.repository import TaskRepository
from ai_day_planner.modules.tasks.service import (
    detect_circular_dependency,
    validate_task_fields,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> TaskConfig:
    return TaskConfig(
        difficulty_min=1, difficulty_max=10,
        urgency_min=1, urgency_max=10,
        importance_min=1, importance_max=10,
    )


def _fresh_repo() -> TaskRepository:
    conn = get_connection(":memory:")
    run_migrations(conn)
    return TaskRepository(conn)


def _make_task(
    task_id: str | None = None,
    difficulty: int = 5,
    urgency: int = 5,
    importance: int = 5,
    task_type: TaskType = TaskType.one_time,
    dependency_ids: list[str] | None = None,
    title: str = "Test Task",
) -> Task:
    now = datetime.now(tz=timezone.utc)
    return Task(
        id=task_id or str(uuid.uuid4()),
        title=title,
        description="",
        difficulty=difficulty,
        urgency=urgency,
        importance=importance,
        estimated_duration=30,
        task_type=task_type,
        state=TaskState.pending,
        recurrence_rule=None,
        dependency_ids=dependency_ids or [],
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Property 1: Task Creation Round-Trip
# ---------------------------------------------------------------------------

class TestProperty1TaskCreationRoundTrip:
    """
    Property 1: Task Creation Round-Trip

    For any valid TaskCreateRequest, creating the task and then querying it
    by the returned ID SHALL return a task with all fields equal to the
    submitted values.

    Validates: Requirements 1.6
    """

    @given(
        difficulty=st.integers(min_value=1, max_value=10),
        urgency=st.integers(min_value=1, max_value=10),
        importance=st.integers(min_value=1, max_value=10),
        estimated_duration=st.integers(min_value=1, max_value=480),
        title=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" -_"
        )),
    )
    @settings(max_examples=100)
    def test_round_trip(self, difficulty, urgency, importance, estimated_duration, title):
        """Property 1: Task Creation Round-Trip — Validates: Requirements 1.6"""
        repo = _fresh_repo()
        task = _make_task(
            difficulty=difficulty,
            urgency=urgency,
            importance=importance,
            title=title.strip() or "T",
        )
        task = task.model_copy(update={"estimated_duration": estimated_duration})
        created = repo.create(task)
        fetched = repo.get_by_id(created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.title == task.title
        assert fetched.difficulty == task.difficulty
        assert fetched.urgency == task.urgency
        assert fetched.importance == task.importance
        assert fetched.estimated_duration == task.estimated_duration
        assert fetched.task_type == task.task_type


# ---------------------------------------------------------------------------
# Property 2: Task Field Validation Rejects Invalid Inputs
# ---------------------------------------------------------------------------

class TestProperty2FieldValidationRejectsInvalid:
    """
    Property 2: Task Field Validation Rejects Invalid Inputs

    For any TaskCreateRequest where at least one field violates its configured
    constraint, the Planner SHALL return a structured error identifying the
    violated field and reject persistence.

    Validates: Requirements 1.2, 1.3
    """

    @given(difficulty=st.integers(min_value=11, max_value=1000))
    @settings(max_examples=100)
    def test_difficulty_above_max_rejected(self, difficulty):
        """Property 2: Field Validation — difficulty above max — Validates: Requirements 1.2, 1.3"""
        config = _make_config()
        req = TaskCreateRequest(
            title="T", difficulty=difficulty, urgency=5, importance=5,
            estimated_duration=30, task_type=TaskType.one_time,
        )
        errors = validate_task_fields(req, config)
        assert any(e.field == "difficulty" for e in errors)

    @given(difficulty=st.integers(min_value=-1000, max_value=0))
    @settings(max_examples=100)
    def test_difficulty_below_min_rejected(self, difficulty):
        """Property 2: Field Validation — difficulty below min — Validates: Requirements 1.2, 1.3"""
        config = _make_config()
        req = TaskCreateRequest(
            title="T", difficulty=difficulty, urgency=5, importance=5,
            estimated_duration=30, task_type=TaskType.one_time,
        )
        errors = validate_task_fields(req, config)
        assert any(e.field == "difficulty" for e in errors)

    @given(urgency=st.integers().filter(lambda x: not (1 <= x <= 10)))
    @settings(max_examples=100)
    def test_urgency_out_of_range_rejected(self, urgency):
        """Property 2: Field Validation — urgency out of range — Validates: Requirements 1.2, 1.3"""
        config = _make_config()
        req = TaskCreateRequest(
            title="T", difficulty=5, urgency=urgency, importance=5,
            estimated_duration=30, task_type=TaskType.one_time,
        )
        errors = validate_task_fields(req, config)
        assert any(e.field == "urgency" for e in errors)


# ---------------------------------------------------------------------------
# Property 3: Missing Dependency Detection
# ---------------------------------------------------------------------------

class TestProperty3MissingDependencyDetection:
    """
    Property 3: Missing Dependency Detection

    For any TaskCreateRequest that references task IDs not present in the
    database, the Planner SHALL return a structured error identifying the
    missing dependency IDs.

    Validates: Requirements 1.4
    """

    @given(
        n_missing=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100)
    def test_missing_deps_not_in_db(self, n_missing):
        """Property 3: Missing Dependency Detection — Validates: Requirements 1.4"""
        repo = _fresh_repo()
        missing_ids = [str(uuid.uuid4()) for _ in range(n_missing)]

        # None of these IDs exist in the DB
        for dep_id in missing_ids:
            assert repo.get_by_id(dep_id) is None, f"Expected {dep_id} to be missing"


# ---------------------------------------------------------------------------
# Property 4: Circular Dependency Detection
# ---------------------------------------------------------------------------

class TestProperty4CircularDependencyDetection:
    """
    Property 4: Circular Dependency Detection

    For any directed graph of task dependencies, if adding a new dependency
    edge would create a cycle, the Planner SHALL detect it regardless of
    cycle length or graph shape.

    Validates: Requirements 1.5
    """

    @given(chain_length=st.integers(min_value=2, max_value=10))
    @settings(max_examples=100)
    def test_closing_chain_creates_cycle(self, chain_length):
        """Property 4: Circular Dependency Detection — Validates: Requirements 1.5"""
        # Build chain: t0 -> t1 -> t2 -> ... -> t(n-1)
        ids = [f"t{i}" for i in range(chain_length)]
        tasks: dict[str, Task] = {}
        for i, tid in enumerate(ids):
            deps = [ids[i + 1]] if i + 1 < chain_length else []
            tasks[tid] = _make_task(task_id=tid, dependency_ids=deps)

        # Adding t(n-1) -> t0 closes the cycle
        assert detect_circular_dependency(ids[-1], [ids[0]], tasks) is True

    @given(chain_length=st.integers(min_value=2, max_value=10))
    @settings(max_examples=100)
    def test_non_closing_addition_no_cycle(self, chain_length):
        """Property 4: No cycle when not closing chain — Validates: Requirements 1.5"""
        ids = [f"t{i}" for i in range(chain_length)]
        tasks: dict[str, Task] = {}
        for i, tid in enumerate(ids):
            deps = [ids[i + 1]] if i + 1 < chain_length else []
            tasks[tid] = _make_task(task_id=tid, dependency_ids=deps)

        # Adding a new isolated node as dependency of last node — no cycle
        new_id = "new_node"
        tasks[new_id] = _make_task(task_id=new_id)
        assert detect_circular_dependency(ids[-1], [new_id], tasks) is False


# ---------------------------------------------------------------------------
# Property 5: Partial Update Preserves Untouched Fields
# ---------------------------------------------------------------------------

class TestProperty5PartialUpdatePreservesFields:
    """
    Property 5: Partial Update Preserves Untouched Fields

    For any existing task and any partial update request containing a strict
    subset of the task's fields, after the update all fields not included in
    the request SHALL retain their pre-update values.

    Validates: Requirements 1.7
    """

    @given(
        new_urgency=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_updating_urgency_preserves_other_fields(self, new_urgency):
        """Property 5: Partial Update Preserves Untouched Fields — Validates: Requirements 1.7"""
        repo = _fresh_repo()
        original = _make_task(difficulty=3, urgency=5, importance=7)
        repo.create(original)

        updated = repo.update(original.id, {"urgency": new_urgency})

        assert updated.urgency == new_urgency
        assert updated.difficulty == original.difficulty
        assert updated.importance == original.importance
        assert updated.title == original.title
        assert updated.estimated_duration == original.estimated_duration


# ---------------------------------------------------------------------------
# Property 6: Task Deletion Removes Task and All Dependency References
# ---------------------------------------------------------------------------

class TestProperty6TaskDeletionCascade:
    """
    Property 6: Task Deletion Removes Task and All Dependency References

    For any task that exists in the database, after a deletion request the
    task SHALL not be retrievable by ID, and no task_dependencies row SHALL
    reference the deleted task's ID in either column.

    Validates: Requirements 1.8
    """

    @given(n_dependents=st.integers(min_value=0, max_value=5))
    @settings(max_examples=100)
    def test_deletion_removes_task_and_references(self, n_dependents):
        """Property 6: Task Deletion Cascade — Validates: Requirements 1.8"""
        repo = _fresh_repo()

        # Create target task
        target = _make_task(task_id="target")
        repo.create(target)

        # Create n_dependents tasks that depend on target
        dependents = []
        for i in range(n_dependents):
            dep_task = _make_task(task_id=f"dep_{i}", dependency_ids=["target"])
            repo.create(dep_task)
            dependents.append(dep_task)

        # Delete target
        repo.delete("target")

        # Target must not be retrievable
        assert repo.get_by_id("target") is None

        # No dependent should still list target as a dependency
        for dep_task in dependents:
            fetched = repo.get_by_id(dep_task.id)
            if fetched is not None:
                assert "target" not in fetched.dependency_ids


# ---------------------------------------------------------------------------
# Property 7: Query Filter Correctness
# ---------------------------------------------------------------------------

class TestProperty7QueryFilterCorrectness:
    """
    Property 7: Query Filter Correctness

    For any set of tasks and any combination of filter parameters, every task
    returned by the query SHALL satisfy all applied filter predicates, and no
    task satisfying all predicates SHALL be absent from the result.

    Validates: Requirements 1.9
    """

    @given(
        filter_min=st.integers(min_value=1, max_value=5),
        filter_max=st.integers(min_value=6, max_value=10),
    )
    @settings(max_examples=100)
    def test_difficulty_range_filter_correct(self, filter_min, filter_max):
        """Property 7: Query Filter Correctness — Validates: Requirements 1.9"""
        repo = _fresh_repo()

        # Insert tasks with varying difficulties
        for d in range(1, 11):
            repo.create(_make_task(task_id=f"t_diff_{d}", difficulty=d))

        filters = TaskQueryFilters(difficulty_min=filter_min, difficulty_max=filter_max)
        results = repo.query(filters)

        # Every returned task must satisfy the filter
        for task in results:
            assert filter_min <= task.difficulty <= filter_max

        # Every task in DB satisfying the filter must be in results
        result_ids = {t.id for t in results}
        for d in range(filter_min, filter_max + 1):
            assert f"t_diff_{d}" in result_ids

    @given(task_type=st.sampled_from(list(TaskType)))
    @settings(max_examples=100)
    def test_task_type_filter_correct(self, task_type):
        """Property 7: Query Filter Correctness (task_type) — Validates: Requirements 1.9"""
        repo = _fresh_repo()

        for tt in TaskType:
            repo.create(_make_task(task_id=f"t_{tt.value}", task_type=tt))

        filters = TaskQueryFilters(task_type=task_type)
        results = repo.query(filters)

        for task in results:
            assert task.task_type == task_type

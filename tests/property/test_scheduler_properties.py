"""
Property-based tests for the Scheduler module.

Properties 12-16 from design.md, validated via Hypothesis.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ai_day_planner.config import FatigueConfig, SchedulerConfig
from ai_day_planner.modules.calendar.models import FreeSlot
from ai_day_planner.modules.calendar.service import _time_to_minutes
from ai_day_planner.modules.scheduler.service import (
    assign_tasks_to_slots,
    compute_priority_score,
)
from ai_day_planner.modules.tasks.models import Task, TaskState, TaskType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sched_config(min_prob: float = 0.4) -> SchedulerConfig:
    return SchedulerConfig(
        weight_difficulty=1.0,
        weight_urgency=1.5,
        weight_importance=1.2,
        weight_fatigue=0.8,
        min_completion_probability=min_prob,
        daily_overload_threshold=0.5,
    )


def _make_fatigue_config() -> FatigueConfig:
    return FatigueConfig(
        min_score=1, max_score=100, high_threshold=75,
        increase_difficulty_weight=0.5, increase_duration_weight=0.05,
        recovery_rate_per_minute=0.1, high_fatigue_penalty=0.2,
    )


def _make_task(
    task_id: str | None = None,
    difficulty: int = 5,
    urgency: int = 5,
    importance: int = 5,
    estimated_duration: int = 60,
    dependency_ids: list[str] | None = None,
) -> Task:
    now = datetime.now(tz=timezone.utc)
    return Task(
        id=task_id or str(uuid.uuid4()),
        title="T",
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


def _make_slot(start_hour: int = 9, duration: int = 120, day: date | None = None) -> FreeSlot:
    d = day or date(2024, 1, 1)
    end_hour = start_hour + duration // 60
    end_min = duration % 60
    return FreeSlot(
        date=d,
        start_time=f"{start_hour:02d}:00",
        end_time=f"{end_hour:02d}:{end_min:02d}",
        duration_minutes=duration,
    )


# ---------------------------------------------------------------------------
# Property 12: Priority Score Ordering
# ---------------------------------------------------------------------------

class TestProperty12PriorityScoreOrdering:
    """
    Property 12: Priority Score Ordering

    For any set of tasks, priority scores must be consistent with the configured
    weighted formula, and tasks SHALL be processed for slot assignment in
    strictly non-increasing priority score order.

    Validates: Requirements 3.1, 3.2
    """

    @given(
        difficulty=st.integers(min_value=1, max_value=10),
        urgency=st.integers(min_value=1, max_value=10),
        importance=st.integers(min_value=1, max_value=10),
        fatigue=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100)
    def test_priority_score_formula(self, difficulty, urgency, importance, fatigue):
        """Property 12: Priority Score Formula — Validates: Requirements 3.1, 3.2"""
        config = _make_sched_config()
        task = _make_task(difficulty=difficulty, urgency=urgency, importance=importance)
        score = compute_priority_score(task, fatigue, config)
        expected = (
            config.weight_difficulty * difficulty
            + config.weight_urgency * urgency
            + config.weight_importance * importance
            - config.weight_fatigue * fatigue
        )
        assert abs(score - expected) < 1e-9

    @given(
        n_tasks=st.integers(min_value=2, max_value=8),
        fatigue=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100)
    def test_assigned_tasks_in_priority_order(self, n_tasks, fatigue):
        """Property 12: Tasks assigned in non-increasing priority order — Validates: Requirements 3.1, 3.2"""
        config = _make_sched_config()
        fatigue_config = _make_fatigue_config()

        tasks = [_make_task(
            task_id=f"t{i}",
            urgency=i + 1,
            estimated_duration=30,
        ) for i in range(n_tasks)]

        # Enough slots for all tasks
        slots = [_make_slot(start_hour=8 + i, duration=60) for i in range(n_tasks)]
        probs = {(t.id, f"2024-01-01 {8+i:02d}:00"): 0.9
                 for i, t in enumerate(tasks)}

        result = assign_tasks_to_slots(
            tasks, slots, fatigue, {}, probs, config, fatigue_config,
        )

        # Verify assigned decisions are in non-increasing priority score order
        scores = [d.priority_score for d in result.assigned]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Property 13: Slot Duration Constraint
# ---------------------------------------------------------------------------

class TestProperty13SlotDurationConstraint:
    """
    Property 13: Slot Duration Constraint

    Every assigned task SHALL have slot_duration_minutes >= task.estimated_duration
    * correction_coefficient.

    Validates: Requirements 3.3
    """

    @given(
        estimated_duration=st.integers(min_value=15, max_value=120),
        correction=st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False),
        slot_duration=st.integers(min_value=15, max_value=240),
    )
    @settings(max_examples=100)
    def test_assigned_slot_duration_sufficient(
        self, estimated_duration, correction, slot_duration
    ):
        """Property 13: Slot Duration Constraint — Validates: Requirements 3.3"""
        config = _make_sched_config()
        fatigue_config = _make_fatigue_config()
        task = _make_task("t1", estimated_duration=estimated_duration)
        slot = FreeSlot(
            date=date(2024, 1, 1),
            start_time="09:00",
            end_time="09:00",  # end_time not used for duration check
            duration_minutes=slot_duration,
        )
        probs = {("t1", "2024-01-01 09:00"): 0.9}

        result = assign_tasks_to_slots(
            [task], [slot], 20, {"t1": correction}, probs, config, fatigue_config,
        )

        effective = estimated_duration * correction
        if slot_duration >= effective:
            # Should be assigned
            assert len(result.assigned) == 1
            assigned_slot = result.assigned[0].slot
            assert assigned_slot.duration_minutes >= effective
        else:
            # Should be deferred (slot too short)
            assert len(result.deferred) == 1


# ---------------------------------------------------------------------------
# Property 14: Probability Threshold Invariant
# ---------------------------------------------------------------------------

class TestProperty14ProbabilityThresholdInvariant:
    """
    Property 14: Probability Threshold Invariant

    Every assigned task SHALL have completion_probability >= min_completion_probability.
    No task with probability below the threshold SHALL appear in the assigned list.

    Validates: Requirements 3.4, 3.5, 7.4
    """

    @given(
        prob=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        threshold=st.floats(min_value=0.1, max_value=0.9, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_probability_threshold_enforced(self, prob, threshold):
        """Property 14: Probability Threshold Invariant — Validates: Requirements 3.4, 3.5, 7.4"""
        config = _make_sched_config(min_prob=threshold)
        fatigue_config = _make_fatigue_config()
        task = _make_task("t1", estimated_duration=30)
        slot = _make_slot(duration=120)
        probs = {("t1", "2024-01-01 09:00"): prob}

        result = assign_tasks_to_slots(
            [task], [slot], 20, {}, probs, config, fatigue_config,
        )

        if prob >= threshold:
            assert len(result.assigned) == 1
            assert result.assigned[0].completion_probability >= threshold
        else:
            assert len(result.assigned) == 0


# ---------------------------------------------------------------------------
# Property 15: Dependency Ordering in Schedule
# ---------------------------------------------------------------------------

class TestProperty15DependencyOrdering:
    """
    Property 15: Dependency Ordering in Schedule

    No task SHALL be assigned a slot that starts before the slot of any of
    its dependency tasks.

    Validates: Requirements 3.6
    """

    def test_dependency_assigned_before_dependent(self):
        """Property 15: Dependency Ordering — Validates: Requirements 3.6"""
        config = _make_sched_config()
        fatigue_config = _make_fatigue_config()

        dep = _make_task("dep", estimated_duration=30)
        dependent = _make_task("dependent", estimated_duration=30, dependency_ids=["dep"])

        # Two slots: 09:00 and 10:00
        slot_early = _make_slot(start_hour=9, duration=60)
        slot_late = _make_slot(start_hour=10, duration=60)

        probs = {
            ("dep", "2024-01-01 09:00"): 0.9,
            ("dep", "2024-01-01 10:00"): 0.9,
            ("dependent", "2024-01-01 09:00"): 0.9,
            ("dependent", "2024-01-01 10:00"): 0.9,
        }

        result = assign_tasks_to_slots(
            [dep, dependent], [slot_early, slot_late], 20, {}, probs, config, fatigue_config,
        )

        if len(result.assigned) == 2:
            dep_decision = next(d for d in result.assigned if d.task_id == "dep")
            dependent_decision = next(d for d in result.assigned if d.task_id == "dependent")
            dep_start = _time_to_minutes(dep_decision.slot.start_time)
            dependent_start = _time_to_minutes(dependent_decision.slot.start_time)
            assert dep_start <= dependent_start


# ---------------------------------------------------------------------------
# Property 16: Dry-Run Idempotence
# ---------------------------------------------------------------------------

class TestProperty16DryRunIdempotence:
    """
    Property 16: Dry-Run Idempotence

    The assign_tasks_to_slots pure function is inherently idempotent —
    calling it multiple times with the same inputs produces the same output
    without any side effects.

    Validates: Requirements 3.8
    """

    @given(
        n_tasks=st.integers(min_value=1, max_value=5),
        fatigue=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100)
    def test_same_inputs_same_output(self, n_tasks, fatigue):
        """Property 16: Dry-Run Idempotence — Validates: Requirements 3.8"""
        config = _make_sched_config()
        fatigue_config = _make_fatigue_config()

        tasks = [_make_task(task_id=f"t{i}", estimated_duration=30) for i in range(n_tasks)]
        slots = [_make_slot(start_hour=8 + i, duration=60) for i in range(n_tasks)]
        probs = {(t.id, f"2024-01-01 {8+i:02d}:00"): 0.9
                 for i, t in enumerate(tasks)}

        result1 = assign_tasks_to_slots(
            tasks, slots, fatigue, {}, probs, config, fatigue_config,
        )
        result2 = assign_tasks_to_slots(
            tasks, slots, fatigue, {}, probs, config, fatigue_config,
        )

        assert len(result1.assigned) == len(result2.assigned)
        assert len(result1.deferred) == len(result2.deferred)
        assert len(result1.skipped) == len(result2.skipped)

        for d1, d2 in zip(result1.assigned, result2.assigned):
            assert d1.task_id == d2.task_id

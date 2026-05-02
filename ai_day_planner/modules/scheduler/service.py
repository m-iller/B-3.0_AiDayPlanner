"""
Pure domain logic for the Scheduler module.

No database access, no side effects. All functions are deterministic.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timezone

from ai_day_planner.config import FatigueConfig, SchedulerConfig
from ai_day_planner.modules.calendar.models import FreeSlot
from ai_day_planner.modules.calendar.service import _time_to_minutes
from ai_day_planner.modules.fatigue.service import apply_high_fatigue_penalty
from ai_day_planner.modules.scheduler.models import ScheduleDecision, ScheduleResult
from ai_day_planner.modules.tasks.models import Task, TaskState


def compute_priority_score(
    task: Task,
    fatigue_score: int,
    config: SchedulerConfig,
) -> float:
    """
    Compute the scheduling priority score for a task.

    Formula (all weights from config):
        score = w_difficulty * difficulty
              + w_urgency    * urgency
              + w_importance * importance
              - w_fatigue    * fatigue_score

    Higher score = scheduled first.
    """
    return (
        config.weight_difficulty * task.difficulty
        + config.weight_urgency * task.urgency
        + config.weight_importance * task.importance
        - config.weight_fatigue * fatigue_score
    )


def apply_fatigue_penalty(
    priority_score: float,
    fatigue_score: int,
    task_difficulty: int,
    config: SchedulerConfig,
    fatigue_config: FatigueConfig,
) -> float:
    """
    Apply high-fatigue penalty to priority score when applicable.

    Delegates to fatigue service pure function.
    """
    return apply_high_fatigue_penalty(
        priority_score, fatigue_score, task_difficulty, config, fatigue_config
    )


def _slot_duration_minutes(slot: FreeSlot) -> int:
    return slot.duration_minutes


def _slot_start_time(slot: FreeSlot) -> time:
    h, m = slot.start_time.split(":")
    return time(int(h), int(m))


def _slot_datetime(slot: FreeSlot) -> datetime:
    """Return a comparable datetime for slot ordering."""
    h, m = slot.start_time.split(":")
    return datetime(
        slot.date.year, slot.date.month, slot.date.day,
        int(h), int(m), tzinfo=timezone.utc,
    )


def assign_tasks_to_slots(
    tasks: list[Task],
    free_slots: list[FreeSlot],
    fatigue_score: int,
    coefficients: dict[str, float],
    probabilities: dict[tuple[str, str], float],
    config: SchedulerConfig,
    fatigue_config: FatigueConfig,
    logger: logging.Logger | None = None,
) -> ScheduleResult:
    """
    Assign unscheduled tasks to free slots using priority-based scheduling.

    Algorithm:
    1. Compute priority score for each task (with fatigue penalty applied).
    2. Sort tasks descending by priority score.
    3. For each task (in order):
       a. For each free slot (chronological):
          - Check slot duration >= estimated_duration * correction_coefficient
          - Check completion_probability >= min_completion_probability
          - Check dependency constraints (all deps completed or scheduled earlier)
          - If all pass: assign task to slot, mark slot consumed
       b. If no slot found: defer task
    4. Return ScheduleResult.

    This is a pure function — no DB access, no event emission.

    Args:
        tasks:          Unscheduled tasks to assign.
        free_slots:     Available free slots (will be consumed as tasks are assigned).
        fatigue_score:  Current fatigue score for the scheduling run.
        coefficients:   dict[task_id, correction_coefficient].
        probabilities:  dict[(task_id, slot_key), completion_probability].
                        slot_key = "YYYY-MM-DD HH:MM"
        config:         SchedulerConfig with weights and thresholds.
        fatigue_config: FatigueConfig for penalty computation.
        logger:         Optional logger for decision logging.

    Returns:
        ScheduleResult with assigned, skipped, and deferred decisions.
    """
    def _log(msg: str, **kwargs) -> None:
        if logger:
            logger.info(msg, extra=kwargs)

    # Step 1 & 2: Score and sort tasks
    scored: list[tuple[float, Task]] = []
    for task in tasks:
        if task.state == TaskState.completed:
            continue
        raw_score = compute_priority_score(task, fatigue_score, config)
        penalized = apply_fatigue_penalty(
            raw_score, fatigue_score, task.difficulty, config, fatigue_config
        )
        scored.append((penalized, task))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Sort free slots chronologically
    available_slots: list[FreeSlot] = sorted(free_slots, key=_slot_datetime)

    # Track which tasks have been assigned (for dependency checking)
    # Maps task_id -> assigned slot datetime (for ordering check)
    assigned_slot_times: dict[str, datetime] = {}

    # Track major tasks assigned per day (date ISO string -> count)
    major_tasks_per_day: dict[str, int] = {}

    assigned: list[ScheduleDecision] = []
    skipped: list[ScheduleDecision] = []
    deferred: list[ScheduleDecision] = []

    # Track consumed slot indices
    consumed_indices: set[int] = set()

    for priority_score, task in scored:
        correction = coefficients.get(task.id, 1.0)
        effective_duration = task.estimated_duration * correction
        slot_found = False

        for idx, slot in enumerate(available_slots):
            if idx in consumed_indices:
                continue

            slot_key = f"{slot.date.isoformat()} {slot.start_time}"

            # Check 1: slot duration sufficient
            if slot.duration_minutes < effective_duration:
                continue

            # Check 2: completion probability threshold
            prob = probabilities.get((task.id, slot_key))
            if prob is None:
                # No probability provided — use a neutral default
                prob = config.min_completion_probability

            if prob < config.min_completion_probability:
                _log(
                    "Slot skipped: probability below threshold",
                    task_id=task.id,
                    slot=slot_key,
                    probability=prob,
                    threshold=config.min_completion_probability,
                    priority_score=priority_score,
                    fatigue_score=fatigue_score,
                    decision_outcome="skipped",
                )
                skipped.append(ScheduleDecision(
                    task_id=task.id,
                    outcome="skipped",
                    slot=slot,
                    priority_score=priority_score,
                    fatigue_score=fatigue_score,
                    completion_probability=prob,
                    reason=f"probability {prob:.3f} < threshold {config.min_completion_probability}",
                ))
                slot_found = True  # counted as processed (skipped, not deferred)
                break

            # Check 3: dependency ordering
            slot_dt = _slot_datetime(slot)
            dep_violated = False
            for dep_id in task.dependency_ids:
                dep_slot_dt = assigned_slot_times.get(dep_id)
                if dep_slot_dt is not None and dep_slot_dt >= slot_dt:
                    dep_violated = True
                    break
                # If dep not yet assigned and not completed — can't schedule this task yet
                # (We only know about tasks passed in; completed tasks are not in the list)

            if dep_violated:
                continue

            # Check 4: major-task-per-day cap (flow-state protection)
            is_major = task.difficulty >= config.major_task_difficulty_threshold
            day_key = slot.date.isoformat()
            if is_major:
                day_major_count = major_tasks_per_day.get(day_key, 0)
                if day_major_count >= config.max_major_tasks_per_day:
                    _log(
                        "Slot skipped: major task cap reached for day",
                        task_id=task.id,
                        slot=slot_key,
                        day=day_key,
                        major_tasks_on_day=day_major_count,
                        cap=config.max_major_tasks_per_day,
                        priority_score=priority_score,
                        fatigue_score=fatigue_score,
                        decision_outcome="skipped",
                    )
                    continue  # try next slot (different day)

            # All checks passed — assign
            consumed_indices.add(idx)
            assigned_slot_times[task.id] = slot_dt
            if is_major:
                major_tasks_per_day[day_key] = major_tasks_per_day.get(day_key, 0) + 1

            _log(
                "Task assigned to slot",
                task_id=task.id,
                slot=slot_key,
                priority_score=priority_score,
                fatigue_score=fatigue_score,
                completion_probability=prob,
                decision_outcome="assigned",
            )
            assigned.append(ScheduleDecision(
                task_id=task.id,
                outcome="assigned",
                slot=slot,
                priority_score=priority_score,
                fatigue_score=fatigue_score,
                completion_probability=prob,
                reason="all constraints satisfied",
            ))
            slot_found = True
            break

        if not slot_found:
            _log(
                "Task deferred: no suitable slot found",
                task_id=task.id,
                priority_score=priority_score,
                fatigue_score=fatigue_score,
                decision_outcome="deferred",
            )
            deferred.append(ScheduleDecision(
                task_id=task.id,
                outcome="deferred",
                slot=None,
                priority_score=priority_score,
                fatigue_score=fatigue_score,
                completion_probability=None,
                reason="no suitable slot found",
            ))

    return ScheduleResult(assigned=assigned, skipped=skipped, deferred=deferred)

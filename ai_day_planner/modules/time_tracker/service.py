"""
Pure domain logic for the Time Tracker module.

No database access, no side effects. All functions are deterministic.
"""

from __future__ import annotations

from datetime import datetime

from ai_day_planner.modules.time_tracker.models import Interruption, TrackingAction
from ai_day_planner.modules.tasks.models import TaskState

# Valid state transitions: (current_state, action) -> new_state
_VALID_TRANSITIONS: dict[tuple[TaskState, TrackingAction], TaskState] = {
    (TaskState.pending,      TrackingAction.start):           TaskState.in_progress,
    (TaskState.in_progress,  TrackingAction.stop):            TaskState.completed,
    (TaskState.in_progress,  TrackingAction.interrupt_start): TaskState.interrupted,
    (TaskState.interrupted,  TrackingAction.interrupt_end):   TaskState.in_progress,
    (TaskState.interrupted,  TrackingAction.stop):            TaskState.completed,
}


def validate_state_transition(
    current_state: TaskState,
    requested_action: TrackingAction,
) -> bool:
    """
    Return True if the requested action is valid from the current state.

    Valid transitions:
        pending      + start           → in_progress
        in_progress  + stop            → completed
        in_progress  + interrupt_start → interrupted
        interrupted  + interrupt_end   → in_progress
        interrupted  + stop            → completed  (auto-closes interruption)
    """
    return (current_state, requested_action) in _VALID_TRANSITIONS


def compute_actual_duration(
    start: datetime,
    end: datetime,
    interruptions: list[Interruption],
) -> int:
    """
    Compute actual working duration in whole minutes.

    Formula:
        actual = (end - start) - sum(interruption.duration_minutes)

    Only closed interruptions (with end_time set) contribute to the total.
    Open interruptions are ignored (caller should close them first).

    Args:
        start:          Session start timestamp.
        end:            Session end timestamp.
        interruptions:  List of Interruption objects (may include open ones).

    Returns:
        Actual duration in whole minutes (minimum 0).
    """
    total_seconds = (end - start).total_seconds()

    interruption_seconds = 0.0
    for intr in interruptions:
        if intr.end_time is not None:
            interruption_seconds += (intr.end_time - intr.start_time).total_seconds()

    actual_seconds = max(0.0, total_seconds - interruption_seconds)
    return int(actual_seconds // 60)

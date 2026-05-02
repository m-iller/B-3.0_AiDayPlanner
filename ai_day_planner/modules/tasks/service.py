"""
Pure domain logic for the Task module.

No database access, no side effects. All functions are deterministic
given the same inputs.
"""

from __future__ import annotations

from collections import deque

from ai_day_planner.config import SchedulerConfig, TaskConfig
from ai_day_planner.modules.tasks.models import (
    FieldValidationError,
    Task,
    TaskCreateRequest,
    TaskType,
)


def validate_task_fields(
    data: TaskCreateRequest,
    config: TaskConfig,
) -> list[FieldValidationError]:
    """
    Validate all task fields against configured constraints.

    Returns a list of ALL violations (not just the first).
    Returns an empty list when all fields are valid.
    """
    errors: list[FieldValidationError] = []

    if not data.title or not data.title.strip():
        errors.append(FieldValidationError(
            field="title",
            constraint="must not be empty",
            received=data.title,
        ))

    if not (config.difficulty_min <= data.difficulty <= config.difficulty_max):
        errors.append(FieldValidationError(
            field="difficulty",
            constraint=f"must be in [{config.difficulty_min}, {config.difficulty_max}]",
            received=data.difficulty,
        ))

    if not (config.urgency_min <= data.urgency <= config.urgency_max):
        errors.append(FieldValidationError(
            field="urgency",
            constraint=f"must be in [{config.urgency_min}, {config.urgency_max}]",
            received=data.urgency,
        ))

    if not (config.importance_min <= data.importance <= config.importance_max):
        errors.append(FieldValidationError(
            field="importance",
            constraint=f"must be in [{config.importance_min}, {config.importance_max}]",
            received=data.importance,
        ))

    if data.estimated_duration <= 0:
        errors.append(FieldValidationError(
            field="estimated_duration",
            constraint="must be > 0",
            received=data.estimated_duration,
        ))

    if data.task_type == TaskType.recurring and data.recurrence_rule is None:
        errors.append(FieldValidationError(
            field="recurrence_rule",
            constraint="required when task_type is 'recurring'",
            received=None,
        ))

    return errors


def detect_circular_dependency(
    task_id: str,
    new_deps: list[str],
    existing_tasks: dict[str, Task],
) -> bool:
    """
    Detect whether adding new_deps to task_id would create a cycle.

    Uses BFS from each new dependency. If task_id is reachable from any
    new dependency (following existing dependency edges), a cycle exists.

    Args:
        task_id:        The task that would gain new dependencies.
        new_deps:       The proposed new dependency IDs.
        existing_tasks: All tasks keyed by ID, with dependency_ids populated.

    Returns:
        True if a cycle would be created, False otherwise.
    """
    # Build adjacency: task -> its dependencies (what it depends on)
    # A cycle exists if task_id is reachable from any node in new_deps
    # following the dependency graph (i.e., new_dep transitively depends on task_id)

    def _reachable_from(start: str) -> set[str]:
        """BFS: all nodes reachable from start via dependency edges."""
        visited: set[str] = set()
        queue: deque[str] = deque([start])
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            task = existing_tasks.get(current)
            if task is not None:
                for dep_id in task.dependency_ids:
                    if dep_id not in visited:
                        queue.append(dep_id)
        return visited

    for dep_id in new_deps:
        reachable = _reachable_from(dep_id)
        if task_id in reachable:
            return True

    return False


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

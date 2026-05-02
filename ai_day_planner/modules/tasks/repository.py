"""
Database repository for the Task module.

All SQL is parameterized. No string interpolation in queries.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from ai_day_planner.modules.tasks.models import (
    RecurrenceRule,
    Task,
    TaskQueryFilters,
    TaskState,
    TaskType,
)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _row_to_task(row: sqlite3.Row, dependency_ids: list[str]) -> Task:
    recurrence_rule = None
    if row["recurrence_rule"]:
        raw = json.loads(row["recurrence_rule"])
        recurrence_rule = RecurrenceRule(**raw)

    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        difficulty=row["difficulty"],
        urgency=row["urgency"],
        importance=row["importance"],
        estimated_duration=row["estimated_duration"],
        task_type=TaskType(row["task_type"]),
        state=TaskState(row["state"]),
        recurrence_rule=recurrence_rule,
        dependency_ids=dependency_ids,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class TaskRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, task: Task) -> Task:
        recurrence_json = (
            task.recurrence_rule.model_dump_json()
            if task.recurrence_rule is not None
            else None
        )
        self._conn.execute(
            """
            INSERT INTO tasks
                (id, title, description, difficulty, urgency, importance,
                 estimated_duration, task_type, state, recurrence_rule,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.title,
                task.description,
                task.difficulty,
                task.urgency,
                task.importance,
                task.estimated_duration,
                task.task_type.value,
                task.state.value,
                recurrence_json,
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
            ),
        )
        for dep_id in task.dependency_ids:
            self._conn.execute(
                "INSERT INTO task_dependencies (task_id, depends_on_id) VALUES (?, ?)",
                (task.id, dep_id),
            )
        self._conn.commit()
        return task

    def get_by_id(self, task_id: str) -> Task | None:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return None
        deps = self.get_dependencies(task_id)
        return _row_to_task(row, deps)

    def update(self, task_id: str, updates: dict) -> Task:
        existing = self.get_by_id(task_id)
        if existing is None:
            raise KeyError(f"Task not found: {task_id}")

        allowed_columns = {
            "title", "description", "difficulty", "urgency", "importance",
            "estimated_duration", "task_type", "state", "recurrence_rule",
        }
        set_clauses: list[str] = []
        params: list = []

        for key, value in updates.items():
            if key not in allowed_columns:
                continue
            if key == "task_type" and hasattr(value, "value"):
                value = value.value
            if key == "state" and hasattr(value, "value"):
                value = value.value
            if key == "recurrence_rule":
                value = value.model_dump_json() if value is not None else None
            set_clauses.append(f"{key} = ?")
            params.append(value)

        if not set_clauses:
            return existing

        set_clauses.append("updated_at = ?")
        params.append(_now_iso())
        params.append(task_id)

        self._conn.execute(
            f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?",  # noqa: S608
            params,
        )

        if "dependency_ids" in updates:
            self._conn.execute(
                "DELETE FROM task_dependencies WHERE task_id = ?", (task_id,)
            )
            for dep_id in updates["dependency_ids"]:
                self._conn.execute(
                    "INSERT INTO task_dependencies (task_id, depends_on_id) VALUES (?, ?)",
                    (task_id, dep_id),
                )

        self._conn.commit()
        updated = self.get_by_id(task_id)
        assert updated is not None
        return updated

    def delete(self, task_id: str) -> None:
        # task_dependencies rows cascade via FK; also delete where this task is a dependency
        self._conn.execute(
            "DELETE FROM task_dependencies WHERE task_id = ? OR depends_on_id = ?",
            (task_id, task_id),
        )
        self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self._conn.commit()

    def query(self, filters: TaskQueryFilters) -> list[Task]:
        conditions: list[str] = []
        params: list = []

        if filters.task_type is not None:
            conditions.append("task_type = ?")
            params.append(filters.task_type.value)
        if filters.difficulty_min is not None:
            conditions.append("difficulty >= ?")
            params.append(filters.difficulty_min)
        if filters.difficulty_max is not None:
            conditions.append("difficulty <= ?")
            params.append(filters.difficulty_max)
        if filters.urgency_min is not None:
            conditions.append("urgency >= ?")
            params.append(filters.urgency_min)
        if filters.urgency_max is not None:
            conditions.append("urgency <= ?")
            params.append(filters.urgency_max)
        if filters.importance_min is not None:
            conditions.append("importance >= ?")
            params.append(filters.importance_min)
        if filters.importance_max is not None:
            conditions.append("importance <= ?")
            params.append(filters.importance_max)
        if filters.is_scheduled is not None:
            if filters.is_scheduled:
                conditions.append(
                    "id IN (SELECT DISTINCT task_id FROM schedule_entries)"
                )
            else:
                conditions.append(
                    "id NOT IN (SELECT DISTINCT task_id FROM schedule_entries)"
                )

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._conn.execute(
            f"SELECT * FROM tasks {where}",  # noqa: S608
            params,
        ).fetchall()

        return [_row_to_task(row, self.get_dependencies(row["id"])) for row in rows]

    def add_dependency(self, task_id: str, depends_on_id: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_id) VALUES (?, ?)",
            (task_id, depends_on_id),
        )
        self._conn.commit()

    def get_dependencies(self, task_id: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT depends_on_id FROM task_dependencies WHERE task_id = ?",
            (task_id,),
        ).fetchall()
        return [row[0] for row in rows]

    def get_all_as_dict(self) -> dict[str, Task]:
        rows = self._conn.execute("SELECT * FROM tasks").fetchall()
        result: dict[str, Task] = {}
        for row in rows:
            deps = self.get_dependencies(row["id"])
            result[row["id"]] = _row_to_task(row, deps)
        return result

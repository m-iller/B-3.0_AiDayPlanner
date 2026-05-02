"""
Database repository for the Learning module.

All SQL is parameterized. No string interpolation in queries.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from ai_day_planner.modules.learning.models import CorrectionCoefficient


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _row_to_coefficient(row: sqlite3.Row) -> CorrectionCoefficient:
    return CorrectionCoefficient(
        task_id=row["task_id"],
        coefficient=row["coefficient"],
        session_count=row["session_count"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
        reset_reason=row["reset_reason"],
    )


class CoefficientRepository:
    def __init__(self, conn: sqlite3.Connection, default_coefficient: float) -> None:
        self._conn = conn
        self._default = default_coefficient

    def get_or_default(self, task_id: str) -> CorrectionCoefficient:
        """Return the coefficient for task_id, or a default record if none exists."""
        row = self._conn.execute(
            "SELECT * FROM correction_coefficients WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row:
            return _row_to_coefficient(row)
        # Return a synthetic default — not persisted until first upsert
        return CorrectionCoefficient(
            task_id=task_id,
            coefficient=self._default,
            session_count=0,
            updated_at=datetime.now(tz=timezone.utc),
        )

    def upsert(self, task_id: str, new_coefficient: float) -> CorrectionCoefficient:
        """Insert or update the coefficient for task_id, incrementing session_count."""
        now = _now_iso()
        existing = self._conn.execute(
            "SELECT session_count FROM correction_coefficients WHERE task_id = ?",
            (task_id,),
        ).fetchone()

        if existing:
            new_count = existing["session_count"] + 1
            self._conn.execute(
                """
                UPDATE correction_coefficients
                SET coefficient = ?, session_count = ?, updated_at = ?, reset_reason = NULL
                WHERE task_id = ?
                """,
                (new_coefficient, new_count, now, task_id),
            )
        else:
            new_count = 1
            self._conn.execute(
                """
                INSERT INTO correction_coefficients
                    (task_id, coefficient, session_count, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, new_coefficient, new_count, now),
            )

        self._conn.commit()
        return CorrectionCoefficient(
            task_id=task_id,
            coefficient=new_coefficient,
            session_count=new_count,
            updated_at=datetime.fromisoformat(now),
        )

    def reset(self, task_id: str, reason: str) -> CorrectionCoefficient:
        """Reset the coefficient for task_id to the configured default."""
        now = _now_iso()
        existing = self._conn.execute(
            "SELECT * FROM correction_coefficients WHERE task_id = ?",
            (task_id,),
        ).fetchone()

        if existing:
            self._conn.execute(
                """
                UPDATE correction_coefficients
                SET coefficient = ?, session_count = 0, updated_at = ?, reset_reason = ?
                WHERE task_id = ?
                """,
                (self._default, now, reason, task_id),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO correction_coefficients
                    (task_id, coefficient, session_count, updated_at, reset_reason)
                VALUES (?, ?, 0, ?, ?)
                """,
                (task_id, self._default, now, reason),
            )

        self._conn.commit()
        return CorrectionCoefficient(
            task_id=task_id,
            coefficient=self._default,
            session_count=0,
            updated_at=datetime.fromisoformat(now),
            reset_reason=reason,
        )

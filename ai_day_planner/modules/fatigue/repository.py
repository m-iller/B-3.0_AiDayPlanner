"""
Database repository for the Fatigue module.

All SQL is parameterized. No string interpolation in queries.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ai_day_planner.modules.fatigue.models import FatigueAuditEntry, FatigueRecord


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _row_to_record(row: sqlite3.Row) -> FatigueRecord:
    return FatigueRecord(
        id=row["id"],
        record_date=row["record_date"],
        score=row["score"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_audit(row: sqlite3.Row) -> FatigueAuditEntry:
    return FatigueAuditEntry(
        id=row["id"],
        record_date=row["record_date"],
        old_score=row["old_score"],
        new_score=row["new_score"],
        cause=row["cause"],
        cause_detail=row["cause_detail"],
        override_reason=row["override_reason"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


class FatigueRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_or_create_for_date(
        self,
        record_date: str,
        initial_score: int,
    ) -> FatigueRecord:
        """Return existing record for date, or create one with initial_score."""
        row = self._conn.execute(
            "SELECT * FROM fatigue_records WHERE record_date = ?",
            (record_date,),
        ).fetchone()
        if row:
            return _row_to_record(row)

        record_id = str(uuid.uuid4())
        now = _now_iso()
        self._conn.execute(
            """
            INSERT INTO fatigue_records (id, record_date, score, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (record_id, record_date, initial_score, now),
        )
        self._conn.commit()
        return FatigueRecord(
            id=record_id,
            record_date=record_date,
            score=initial_score,
            updated_at=datetime.fromisoformat(now),
        )

    def update_score(
        self,
        record_date: str,
        new_score: int,
        cause: str,
        cause_detail: Optional[dict[str, Any]] = None,
        override_reason: Optional[str] = None,
    ) -> FatigueRecord:
        """Update the fatigue score for a date and write an audit entry."""
        existing = self._conn.execute(
            "SELECT * FROM fatigue_records WHERE record_date = ?",
            (record_date,),
        ).fetchone()
        if existing is None:
            raise KeyError(f"No fatigue record for date: {record_date}")

        old_score = existing["score"]
        now = _now_iso()

        self._conn.execute(
            "UPDATE fatigue_records SET score = ?, updated_at = ? WHERE record_date = ?",
            (new_score, now, record_date),
        )

        audit_id = str(uuid.uuid4())
        self._conn.execute(
            """
            INSERT INTO fatigue_audit
                (id, record_date, old_score, new_score, cause,
                 cause_detail, override_reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                record_date,
                old_score,
                new_score,
                cause,
                json.dumps(cause_detail) if cause_detail else None,
                override_reason,
                now,
            ),
        )
        self._conn.commit()

        return FatigueRecord(
            id=existing["id"],
            record_date=record_date,
            score=new_score,
            updated_at=datetime.fromisoformat(now),
        )

    def get_audit_log(self, record_date: str) -> list[FatigueAuditEntry]:
        rows = self._conn.execute(
            "SELECT * FROM fatigue_audit WHERE record_date = ? ORDER BY created_at",
            (record_date,),
        ).fetchall()
        return [_row_to_audit(r) for r in rows]

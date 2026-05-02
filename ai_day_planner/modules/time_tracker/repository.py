"""
Database repository for the Time Tracker module.

All SQL is parameterized. No string interpolation in queries.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from ai_day_planner.modules.time_tracker.models import Interruption, TrackingSession


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.fromisoformat(value)


class InterruptionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, session_id: str, start_time: datetime) -> Interruption:
        intr_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO interruptions (id, session_id, start_time) VALUES (?, ?, ?)",
            (intr_id, session_id, start_time.isoformat()),
        )
        self._conn.commit()
        return Interruption(id=intr_id, session_id=session_id, start_time=start_time)

    def close(self, interruption_id: str, end_time: datetime) -> Interruption:
        row = self._conn.execute(
            "SELECT * FROM interruptions WHERE id = ?", (interruption_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Interruption not found: {interruption_id}")

        start = datetime.fromisoformat(row["start_time"])
        duration = int((end_time - start).total_seconds() // 60)

        self._conn.execute(
            "UPDATE interruptions SET end_time = ?, duration_minutes = ? WHERE id = ?",
            (end_time.isoformat(), duration, interruption_id),
        )
        self._conn.commit()
        return Interruption(
            id=interruption_id,
            session_id=row["session_id"],
            start_time=start,
            end_time=end_time,
            duration_minutes=duration,
        )

    def get_for_session(self, session_id: str) -> list[Interruption]:
        rows = self._conn.execute(
            "SELECT * FROM interruptions WHERE session_id = ? ORDER BY start_time",
            (session_id,),
        ).fetchall()
        return [
            Interruption(
                id=r["id"],
                session_id=r["session_id"],
                start_time=datetime.fromisoformat(r["start_time"]),
                end_time=_parse_dt(r["end_time"]),
                duration_minutes=r["duration_minutes"],
            )
            for r in rows
        ]

    def get_open_for_session(self, session_id: str) -> Optional[Interruption]:
        """Return the open (unclosed) interruption for a session, if any."""
        row = self._conn.execute(
            "SELECT * FROM interruptions WHERE session_id = ? AND end_time IS NULL",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return Interruption(
            id=row["id"],
            session_id=row["session_id"],
            start_time=datetime.fromisoformat(row["start_time"]),
        )


class TrackingSessionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._interruptions = InterruptionRepository(conn)

    def create(self, task_id: str, start_time: datetime) -> TrackingSession:
        session_id = str(uuid.uuid4())
        self._conn.execute(
            """
            INSERT INTO tracking_sessions (id, task_id, start_time, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, task_id, start_time.isoformat(), _now_iso()),
        )
        self._conn.commit()
        return TrackingSession(id=session_id, task_id=task_id, start_time=start_time)

    def close(
        self,
        session_id: str,
        end_time: datetime,
        actual_duration: int,
    ) -> TrackingSession:
        self._conn.execute(
            "UPDATE tracking_sessions SET end_time = ?, actual_duration = ? WHERE id = ?",
            (end_time.isoformat(), actual_duration, session_id),
        )
        self._conn.commit()
        return self.get_by_id(session_id)  # type: ignore[return-value]

    def get_by_id(self, session_id: str) -> Optional[TrackingSession]:
        row = self._conn.execute(
            "SELECT * FROM tracking_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        interruptions = self._interruptions.get_for_session(session_id)
        return TrackingSession(
            id=row["id"],
            task_id=row["task_id"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=_parse_dt(row["end_time"]),
            actual_duration=row["actual_duration"],
            interruptions=interruptions,
        )

    def get_by_task_id(self, task_id: str) -> list[TrackingSession]:
        rows = self._conn.execute(
            "SELECT * FROM tracking_sessions WHERE task_id = ? ORDER BY start_time",
            (task_id,),
        ).fetchall()
        return [
            TrackingSession(
                id=r["id"],
                task_id=r["task_id"],
                start_time=datetime.fromisoformat(r["start_time"]),
                end_time=_parse_dt(r["end_time"]),
                actual_duration=r["actual_duration"],
                interruptions=self._interruptions.get_for_session(r["id"]),
            )
            for r in rows
        ]

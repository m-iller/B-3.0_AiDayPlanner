"""
Database repository for the Calendar module.

All SQL is parameterized. No string interpolation in queries.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import date, datetime, timezone

from ai_day_planner.modules.calendar.models import (
    ScheduleEntry,
    TimeBlock,
)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _row_to_time_block(row: sqlite3.Row) -> TimeBlock:
    return TimeBlock(
        id=row["id"],
        day_of_week=row["day_of_week"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        label=row["label"],
        is_recurring=bool(row["is_recurring"]),
        week_number=row["week_number"],
        year=row["year"],
    )


def _row_to_schedule_entry(row: sqlite3.Row) -> ScheduleEntry:
    return ScheduleEntry(
        id=row["id"],
        task_id=row["task_id"],
        scheduled_date=date.fromisoformat(row["scheduled_date"]),
        slot_start=row["slot_start"],
        slot_end=row["slot_end"],
        is_confirmed=bool(row["is_confirmed"]),
    )


class TimeBlockRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, block: TimeBlock) -> TimeBlock:
        self._conn.execute(
            """
            INSERT INTO time_blocks
                (id, day_of_week, start_time, end_time, label,
                 is_recurring, week_number, year, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                block.id,
                block.day_of_week,
                block.start_time,
                block.end_time,
                block.label,
                int(block.is_recurring),
                block.week_number,
                block.year,
                _now_iso(),
            ),
        )
        self._conn.commit()
        return block

    def get_by_id(self, block_id: str) -> TimeBlock | None:
        row = self._conn.execute(
            "SELECT * FROM time_blocks WHERE id = ?", (block_id,)
        ).fetchone()
        return _row_to_time_block(row) if row else None

    def delete(self, block_id: str) -> None:
        self._conn.execute("DELETE FROM time_blocks WHERE id = ?", (block_id,))
        self._conn.commit()

    def get_for_day(self, day_of_week: int) -> list[TimeBlock]:
        rows = self._conn.execute(
            "SELECT * FROM time_blocks WHERE day_of_week = ?", (day_of_week,)
        ).fetchall()
        return [_row_to_time_block(r) for r in rows]

    def get_for_week(self, week_number: int, year: int) -> list[TimeBlock]:
        rows = self._conn.execute(
            """
            SELECT * FROM time_blocks
            WHERE is_recurring = 1
               OR (week_number = ? AND year = ?)
            """,
            (week_number, year),
        ).fetchall()
        return [_row_to_time_block(r) for r in rows]

    def get_all(self) -> list[TimeBlock]:
        rows = self._conn.execute("SELECT * FROM time_blocks").fetchall()
        return [_row_to_time_block(r) for r in rows]


class ScheduleEntryRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, entry: ScheduleEntry) -> ScheduleEntry:
        self._conn.execute(
            """
            INSERT INTO schedule_entries
                (id, task_id, scheduled_date, slot_start, slot_end,
                 is_confirmed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.task_id,
                entry.scheduled_date.isoformat(),
                entry.slot_start,
                entry.slot_end,
                int(entry.is_confirmed),
                _now_iso(),
            ),
        )
        self._conn.commit()
        return entry

    def get_for_day(self, day: date) -> list[ScheduleEntry]:
        rows = self._conn.execute(
            "SELECT * FROM schedule_entries WHERE scheduled_date = ?",
            (day.isoformat(),),
        ).fetchall()
        return [_row_to_schedule_entry(r) for r in rows]

    def get_for_week(self, week_number: int, year: int) -> list[ScheduleEntry]:
        # Compute the ISO week's Monday date and collect 7 days
        from datetime import timedelta
        jan4 = date(year, 1, 4)
        week_start = jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=week_number - 1)
        dates = [week_start + timedelta(days=i) for i in range(7)]
        date_strs = [d.isoformat() for d in dates]
        placeholders = ",".join("?" * len(date_strs))
        rows = self._conn.execute(
            f"SELECT * FROM schedule_entries WHERE scheduled_date IN ({placeholders})",  # noqa: S608
            date_strs,
        ).fetchall()
        return [_row_to_schedule_entry(r) for r in rows]

    def delete(self, entry_id: str) -> None:
        self._conn.execute(
            "DELETE FROM schedule_entries WHERE id = ?", (entry_id,)
        )
        self._conn.commit()

    def confirm(self, entry_id: str) -> None:
        self._conn.execute(
            "UPDATE schedule_entries SET is_confirmed = 1 WHERE id = ?",
            (entry_id,),
        )
        self._conn.commit()

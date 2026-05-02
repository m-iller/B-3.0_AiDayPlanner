"""
Unit tests for ai_day_planner/database.py

Covers:
- run_migrations creates all 9 expected tables
- run_migrations is idempotent (safe to call twice)
- Foreign key constraints are enforced
- WAL journal mode is enabled
"""

from __future__ import annotations

import sqlite3

import pytest

from ai_day_planner.database import (
    _EXPECTED_TABLES,
    get_connection,
    run_migrations,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    ).fetchall()
    return {row[0] for row in rows}


# ---------------------------------------------------------------------------
# Tests: Table creation
# ---------------------------------------------------------------------------

class TestRunMigrations:
    def test_creates_all_nine_tables(self):
        conn = get_connection(":memory:")
        run_migrations(conn)
        assert _table_names(conn) == _EXPECTED_TABLES

    def test_creates_tasks_table(self):
        conn = get_connection(":memory:")
        run_migrations(conn)
        assert "tasks" in _table_names(conn)

    def test_creates_task_dependencies_table(self):
        conn = get_connection(":memory:")
        run_migrations(conn)
        assert "task_dependencies" in _table_names(conn)

    def test_creates_time_blocks_table(self):
        conn = get_connection(":memory:")
        run_migrations(conn)
        assert "time_blocks" in _table_names(conn)

    def test_creates_schedule_entries_table(self):
        conn = get_connection(":memory:")
        run_migrations(conn)
        assert "schedule_entries" in _table_names(conn)

    def test_creates_fatigue_records_table(self):
        conn = get_connection(":memory:")
        run_migrations(conn)
        assert "fatigue_records" in _table_names(conn)

    def test_creates_fatigue_audit_table(self):
        conn = get_connection(":memory:")
        run_migrations(conn)
        assert "fatigue_audit" in _table_names(conn)

    def test_creates_tracking_sessions_table(self):
        conn = get_connection(":memory:")
        run_migrations(conn)
        assert "tracking_sessions" in _table_names(conn)

    def test_creates_interruptions_table(self):
        conn = get_connection(":memory:")
        run_migrations(conn)
        assert "interruptions" in _table_names(conn)

    def test_creates_correction_coefficients_table(self):
        conn = get_connection(":memory:")
        run_migrations(conn)
        assert "correction_coefficients" in _table_names(conn)


# ---------------------------------------------------------------------------
# Tests: Idempotence
# ---------------------------------------------------------------------------

class TestIdempotence:
    def test_run_migrations_twice_does_not_raise(self):
        conn = get_connection(":memory:")
        run_migrations(conn)
        run_migrations(conn)  # must not raise

    def test_run_migrations_twice_same_tables(self):
        conn = get_connection(":memory:")
        run_migrations(conn)
        tables_first = _table_names(conn)
        run_migrations(conn)
        tables_second = _table_names(conn)
        assert tables_first == tables_second

    def test_run_migrations_ten_times_stable(self):
        conn = get_connection(":memory:")
        for _ in range(10):
            run_migrations(conn)
        assert _table_names(conn) == _EXPECTED_TABLES


# ---------------------------------------------------------------------------
# Tests: Foreign key enforcement
# ---------------------------------------------------------------------------

class TestForeignKeys:
    def _seeded_conn(self) -> sqlite3.Connection:
        conn = get_connection(":memory:")
        run_migrations(conn)
        return conn

    def test_fk_enforced_task_dependencies_missing_task(self):
        conn = self._seeded_conn()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO task_dependencies (task_id, depends_on_id) VALUES (?, ?);",
                ("nonexistent-task", "also-nonexistent"),
            )
            conn.commit()

    def test_fk_enforced_schedule_entries_missing_task(self):
        conn = self._seeded_conn()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO schedule_entries
                   (id, task_id, scheduled_date, slot_start, slot_end, is_confirmed, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?);""",
                ("se-1", "ghost-task", "2024-01-01", "09:00", "10:00", 0, "2024-01-01T00:00:00Z"),
            )
            conn.commit()

    def test_fk_cascade_delete_task_removes_dependencies(self):
        conn = self._seeded_conn()
        # Insert parent task
        conn.execute(
            """INSERT INTO tasks
               (id, title, difficulty, urgency, importance, estimated_duration,
                task_type, state, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            ("t1", "Task 1", 3, 3, 3, 30, "one_time", "pending",
             "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
        )
        conn.execute(
            """INSERT INTO tasks
               (id, title, difficulty, urgency, importance, estimated_duration,
                task_type, state, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            ("t2", "Task 2", 3, 3, 3, 30, "one_time", "pending",
             "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO task_dependencies (task_id, depends_on_id) VALUES (?, ?);",
            ("t2", "t1"),
        )
        conn.commit()

        # Delete t1 — dependency row should cascade
        conn.execute("DELETE FROM tasks WHERE id = ?;", ("t1",))
        conn.commit()

        rows = conn.execute("SELECT * FROM task_dependencies WHERE depends_on_id = 't1';").fetchall()
        assert rows == []

    def test_fk_cascade_delete_session_removes_interruptions(self):
        conn = self._seeded_conn()
        conn.execute(
            """INSERT INTO tasks
               (id, title, difficulty, urgency, importance, estimated_duration,
                task_type, state, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            ("t3", "Task 3", 2, 2, 2, 20, "one_time", "pending",
             "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
        )
        conn.execute(
            """INSERT INTO tracking_sessions
               (id, task_id, start_time, created_at)
               VALUES (?, ?, ?, ?);""",
            ("s1", "t3", "2024-01-01T09:00:00Z", "2024-01-01T09:00:00Z"),
        )
        conn.execute(
            """INSERT INTO interruptions (id, session_id, start_time)
               VALUES (?, ?, ?);""",
            ("i1", "s1", "2024-01-01T09:30:00Z"),
        )
        conn.commit()

        conn.execute("DELETE FROM tracking_sessions WHERE id = ?;", ("s1",))
        conn.commit()

        rows = conn.execute("SELECT * FROM interruptions WHERE session_id = 's1';").fetchall()
        assert rows == []


# ---------------------------------------------------------------------------
# Tests: WAL mode
# ---------------------------------------------------------------------------

class TestWalMode:
    def test_wal_mode_enabled(self):
        conn = get_connection(":memory:")
        # In-memory DBs report "memory" not "wal", but file DBs do.
        # We verify the PRAGMA was accepted without error and the connection works.
        result = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        # :memory: always returns "memory"; for file DBs it would be "wal"
        assert result in ("wal", "memory")

    def test_wal_mode_on_file_db(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        conn = get_connection(db_file)
        result = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert result == "wal"

    def test_foreign_keys_pragma_on(self):
        conn = get_connection(":memory:")
        result = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert result == 1

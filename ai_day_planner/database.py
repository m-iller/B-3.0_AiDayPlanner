"""
SQLite connection factory and schema migrations for AI Day Planner.

get_connection: opens a connection with WAL mode and FK enforcement.
run_migrations: creates all 9 tables using CREATE TABLE IF NOT EXISTS (idempotent).
"""

from __future__ import annotations

import sqlite3


def get_connection(db_path: str, check_same_thread: bool = True) -> sqlite3.Connection:
    """
    Open a SQLite connection with WAL journal mode and foreign key enforcement.

    Args:
        db_path: File path for the SQLite database, or ":memory:" for in-memory.
        check_same_thread: Set False to allow use across threads (safe for read-heavy
            workloads with WAL mode; each request should still use its own connection).

    Returns:
        A configured sqlite3.Connection.
    """
    conn = sqlite3.connect(db_path, check_same_thread=check_same_thread)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


_MIGRATIONS: list[str] = [
    # 1. Tasks
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id                  TEXT PRIMARY KEY,
        title               TEXT NOT NULL,
        description         TEXT NOT NULL DEFAULT '',
        difficulty          INTEGER NOT NULL,
        urgency             INTEGER NOT NULL,
        importance          INTEGER NOT NULL,
        estimated_duration  INTEGER NOT NULL,
        task_type           TEXT NOT NULL,
        state               TEXT NOT NULL DEFAULT 'pending',
        recurrence_rule     TEXT,
        created_at          TEXT NOT NULL,
        updated_at          TEXT NOT NULL
    );
    """,

    # 2. Task dependencies (many-to-many)
    """
    CREATE TABLE IF NOT EXISTS task_dependencies (
        task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        depends_on_id   TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        PRIMARY KEY (task_id, depends_on_id)
    );
    """,

    # 3. Time blocks
    """
    CREATE TABLE IF NOT EXISTS time_blocks (
        id              TEXT PRIMARY KEY,
        day_of_week     INTEGER NOT NULL,
        start_time      TEXT NOT NULL,
        end_time        TEXT NOT NULL,
        label           TEXT NOT NULL,
        is_recurring    INTEGER NOT NULL DEFAULT 1,
        week_number     INTEGER,
        year            INTEGER,
        created_at      TEXT NOT NULL
    );
    """,

    # 4. Schedule entries
    """
    CREATE TABLE IF NOT EXISTS schedule_entries (
        id              TEXT PRIMARY KEY,
        task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        scheduled_date  TEXT NOT NULL,
        slot_start      TEXT NOT NULL,
        slot_end        TEXT NOT NULL,
        is_confirmed    INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL
    );
    """,

    # 5. Fatigue records (one per tracked day)
    """
    CREATE TABLE IF NOT EXISTS fatigue_records (
        id              TEXT PRIMARY KEY,
        record_date     TEXT NOT NULL UNIQUE,
        score           INTEGER NOT NULL,
        updated_at      TEXT NOT NULL
    );
    """,

    # 6. Fatigue audit log
    """
    CREATE TABLE IF NOT EXISTS fatigue_audit (
        id              TEXT PRIMARY KEY,
        record_date     TEXT NOT NULL,
        old_score       INTEGER NOT NULL,
        new_score       INTEGER NOT NULL,
        cause           TEXT NOT NULL,
        cause_detail    TEXT,
        override_reason TEXT,
        created_at      TEXT NOT NULL
    );
    """,

    # 7. Tracking sessions
    """
    CREATE TABLE IF NOT EXISTS tracking_sessions (
        id              TEXT PRIMARY KEY,
        task_id         TEXT NOT NULL REFERENCES tasks(id),
        start_time      TEXT NOT NULL,
        end_time        TEXT,
        actual_duration INTEGER,
        created_at      TEXT NOT NULL
    );
    """,

    # 8. Interruptions
    """
    CREATE TABLE IF NOT EXISTS interruptions (
        id               TEXT PRIMARY KEY,
        session_id       TEXT NOT NULL REFERENCES tracking_sessions(id) ON DELETE CASCADE,
        start_time       TEXT NOT NULL,
        end_time         TEXT,
        duration_minutes INTEGER
    );
    """,

    # 9. Correction coefficients (one per task)
    """
    CREATE TABLE IF NOT EXISTS correction_coefficients (
        task_id         TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
        coefficient     REAL NOT NULL,
        session_count   INTEGER NOT NULL DEFAULT 0,
        updated_at      TEXT NOT NULL,
        reset_reason    TEXT
    );
    """,
]

_EXPECTED_TABLES = {
    "tasks",
    "task_dependencies",
    "time_blocks",
    "schedule_entries",
    "fatigue_records",
    "fatigue_audit",
    "tracking_sessions",
    "interruptions",
    "correction_coefficients",
}


def run_migrations(conn: sqlite3.Connection) -> None:
    """
    Create all 9 application tables if they do not already exist.

    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS throughout.

    Args:
        conn: An open sqlite3.Connection (should have FK enforcement enabled).
    """
    cursor = conn.cursor()
    for statement in _MIGRATIONS:
        cursor.execute(statement)
    conn.commit()

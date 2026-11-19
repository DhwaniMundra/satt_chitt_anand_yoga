"""SQLite storage: one file, created on first use. Times are stored as UTC ISO-8601 strings."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL CHECK (role IN ('student', 'teacher')),
  status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
  pw_hash TEXT NOT NULL,
  lang TEXT NOT NULL DEFAULT 'en',
  research_consent INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tokens (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS class_sessions (
  id INTEGER PRIMARY KEY,
  class_key TEXT NOT NULL,
  starts_at TEXT NOT NULL UNIQUE,
  duration_min INTEGER NOT NULL,
  meet_link TEXT,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checkins (
  user_id INTEGER NOT NULL REFERENCES users(id),
  session_id INTEGER NOT NULL REFERENCES class_sessions(id),
  phase TEXT NOT NULL CHECK (phase IN ('before', 'after')),
  mood INTEGER NOT NULL CHECK (mood BETWEEN 1 AND 5),
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, session_id, phase)
);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  screen TEXT NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),  -- NULL unless the person gave research consent
  lang TEXT NOT NULL,
  question TEXT,
  sources TEXT NOT NULL,
  mode TEXT NOT NULL,
  latency_s REAL NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  role TEXT NOT NULL CHECK (role IN ('student', 'companion')),
  text TEXT NOT NULL,
  tools TEXT NOT NULL DEFAULT '[]',
  mode TEXT NOT NULL DEFAULT 'companion',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS companion_notes (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  text TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""

# Tables copied to the backup, in an order that respects foreign keys. Left out on purpose: login tokens, and each
# student's chat with the companion and the notes it keeps for them, which are theirs alone.
BACKUP_TABLES = ["users", "class_sessions", "checkins", "feedback", "questions", "settings"]


def now() -> datetime:
    return datetime.now(UTC)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def connect(path: Path) -> sqlite3.Connection:
    """Opens (and if needed creates) the database at `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(chat_messages)")}
    if "mode" not in columns:  # databases made before replies kept their kind (urgent, notes, companion)
        conn.execute("ALTER TABLE chat_messages ADD COLUMN mode TEXT NOT NULL DEFAULT 'companion'")
    return conn


def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def export_rows(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Every backed-up table as a list of row dicts."""
    return {table: [dict(row) for row in conn.execute(f"SELECT * FROM {table}")] for table in BACKUP_TABLES}


def import_rows(conn: sqlite3.Connection, data: dict[str, list[dict]]) -> None:
    """Loads rows written by `export_rows`. A row already present (such as a setting made at start-up) is
    replaced by the backed-up one."""
    for table in BACKUP_TABLES:
        for row in data.get(table, []):
            columns = ", ".join(row)
            marks = ", ".join("?" for _ in row)
            conn.execute(f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({marks})", tuple(row.values()))
    conn.commit()


def is_empty(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0

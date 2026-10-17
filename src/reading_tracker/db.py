"""SQLite schema, connection, and small read/write helpers.

The database stores raw events only: books and reading sessions. Anything
derived (duration, pace, fraction complete) is computed in ``features.py``.
"""

import sqlite3
from pathlib import Path

import pandas as pd


def _is_project_root(directory: Path) -> bool:
    return (directory / "pyproject.toml").is_file() and (
        directory / "src" / "reading_tracker"
    ).is_dir()


def find_project_root(start: Path | None = None) -> Path:
    """Return the repo root: the closest folder holding this project's files.

    Searches upward from ``start`` (default: this file), then from the current
    working directory, for a folder with both ``pyproject.toml`` and
    ``src/reading_tracker/``. Falls back to the working directory, which is the
    repo root when the Streamlit apps are launched from it.
    """
    cwd = Path.cwd().resolve()
    for origin in (Path(start or __file__).resolve(), cwd):
        for directory in (origin, *origin.parents):
            if _is_project_root(directory):
                return directory
    return cwd


PROJECT_ROOT = find_project_root()
RAW_DB_PATH = PROJECT_ROOT / "data" / "raw" / "reading.db"
DEMO_DB_PATH = PROJECT_ROOT / "data" / "demo" / "demo.db"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    book_id        INTEGER PRIMARY KEY,
    title          TEXT NOT NULL,
    author         TEXT,
    genre          TEXT,
    language       TEXT,     -- e.g. 'English', 'Vietnamese'
    format         TEXT CHECK (format IN ('physical', 'ebook', 'audio')),
    progress_unit  TEXT CHECK (progress_unit IN ('page', 'percent')),
    total_pages    INTEGER,  -- print-equivalent page count, also for ebooks
    added_at       TEXT NOT NULL,
    status         TEXT CHECK (status IN ('reading', 'finished', 'abandoned'))
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id  INTEGER PRIMARY KEY,
    book_id     INTEGER NOT NULL REFERENCES books (book_id),
    started_at  TEXT NOT NULL,
    ended_at    TEXT,           -- NULL means the session is active
    start_pos   REAL NOT NULL,  -- page number or percent, per books.progress_unit
    end_pos     REAL,
    note        TEXT
);

-- At most one active session: every active row gets the same index key,
-- so inserting (or reopening) a second one violates uniqueness.
CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_one_active
    ON sessions ((ended_at IS NULL))
    WHERE ended_at IS NULL;
"""


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the tables and index if they don't exist yet. Safe to call twice.

    Like any ``executescript`` call, this first commits a pending transaction,
    so call it on a fresh connection rather than in the middle of a write.
    """
    conn.executescript(SCHEMA)


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a SQLite database with foreign keys on and the schema in place.

    Parameters
    ----------
    db_path
        Path to the database file, by default the private ``RAW_DB_PATH``.
        Missing parent folders are created.

    Returns
    -------
    sqlite3.Connection
        Connection returning ``sqlite3.Row`` rows (columns accessible by name).
        The caller is responsible for closing it.
    """
    db_path = Path(RAW_DB_PATH if db_path is None else db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)
    except BaseException:
        conn.close()
        raise
    return conn


def read_books(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return the ``books`` table as a DataFrame, ordered by ``book_id``."""
    return pd.read_sql_query("SELECT * FROM books ORDER BY book_id", conn)


def read_sessions(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return the ``sessions`` table as a DataFrame, ordered by ``session_id``."""
    return pd.read_sql_query("SELECT * FROM sessions ORDER BY session_id", conn)

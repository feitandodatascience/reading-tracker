"""Tests for the SQLite schema and connection helper."""

import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from reading_tracker import db

STARTED_AT = "2026-10-01T20:00:00+02:00"
ENDED_AT = "2026-10-01T20:45:00+02:00"
REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    yield connection
    connection.close()


def insert_book(conn: sqlite3.Connection, **overrides) -> int:
    values = {
        "title": "Dune",
        "format": "physical",
        "progress_unit": "page",
        "total_pages": 600,
        "added_at": STARTED_AT,
        "status": "reading",
        **overrides,
    }
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    cursor = conn.execute(
        f"INSERT INTO books ({columns}) VALUES ({placeholders})",
        tuple(values.values()),
    )
    return cursor.lastrowid


def insert_session(
    conn: sqlite3.Connection, book_id: int, ended_at: str | None = None
) -> int:
    cursor = conn.execute(
        "INSERT INTO sessions (book_id, started_at, ended_at, start_pos)"
        " VALUES (?, ?, ?, ?)",
        (book_id, STARTED_AT, ended_at, 1),
    )
    return cursor.lastrowid


def table_info(conn: sqlite3.Connection, table: str) -> list[tuple]:
    """Return (name, type, notnull, pk) for each column of ``table``."""
    rows = conn.execute(f"PRAGMA table_info({table})")
    return [(r["name"], r["type"], r["notnull"], r["pk"]) for r in rows]


# --- connection --------------------------------------------------------------


def test_connect_creates_missing_parent_folders(tmp_path):
    path = tmp_path / "nested" / "folder" / "reading.db"
    db.connect(path).close()
    assert path.is_file()


def test_connect_enables_foreign_keys(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_connect_reads_default_path_at_call_time(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "RAW_DB_PATH", tmp_path / "patched.db")
    db.connect().close()
    assert (tmp_path / "patched.db").is_file()


def test_connect_closes_connection_when_schema_fails(tmp_path):
    path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(path)
    legacy.execute(
        "CREATE TABLE sessions (session_id INTEGER PRIMARY KEY, ended_at TEXT)"
    )
    legacy.executemany("INSERT INTO sessions (ended_at) VALUES (?)", [(None,)] * 2)
    legacy.commit()
    legacy.close()

    with pytest.raises(sqlite3.IntegrityError):
        db.connect(path)
    path.unlink()  # fails on Windows if connect() leaked an open handle


# --- schema --------------------------------------------------------------------


def test_schema_matches_data_model(conn):
    assert table_info(conn, "books") == [
        ("book_id", "INTEGER", 0, 1),
        ("title", "TEXT", 1, 0),
        ("author", "TEXT", 0, 0),
        ("genre", "TEXT", 0, 0),
        ("language", "TEXT", 0, 0),
        ("format", "TEXT", 0, 0),
        ("progress_unit", "TEXT", 0, 0),
        ("total_pages", "INTEGER", 0, 0),
        ("added_at", "TEXT", 1, 0),
        ("status", "TEXT", 0, 0),
    ]
    assert table_info(conn, "sessions") == [
        ("session_id", "INTEGER", 0, 1),
        ("book_id", "INTEGER", 1, 0),
        ("started_at", "TEXT", 1, 0),
        ("ended_at", "TEXT", 0, 0),
        ("start_pos", "REAL", 1, 0),
        ("end_pos", "REAL", 0, 0),
        ("note", "TEXT", 0, 0),
    ]


def test_create_schema_is_idempotent_and_keeps_data(tmp_path):
    path = tmp_path / "test.db"
    with db.connect(path) as conn:
        insert_book(conn)
    conn.close()

    conn = db.connect(path)
    db.create_schema(conn)
    db.create_schema(conn)
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 1
    conn.close()


def test_session_requires_existing_book(conn):
    with pytest.raises(sqlite3.IntegrityError):
        insert_session(conn, book_id=999)


def test_book_title_is_required(conn):
    with pytest.raises(sqlite3.IntegrityError):
        insert_book(conn, title=None)


@pytest.mark.parametrize(
    ("column", "value"),
    [("format", "comic"), ("progress_unit", "chapter"), ("status", "paused")],
)
def test_check_constraints_reject_unknown_values(conn, column, value):
    with pytest.raises(sqlite3.IntegrityError):
        insert_book(conn, **{column: value})


# --- one active session --------------------------------------------------------


def test_only_one_active_session_is_allowed(conn):
    book_id = insert_book(conn)
    other_book_id = insert_book(conn, title="Piranesi")
    insert_session(conn, book_id)
    with pytest.raises(sqlite3.IntegrityError):
        insert_session(conn, other_book_id)


def test_reopening_a_session_while_another_is_active_fails(conn):
    book_id = insert_book(conn)
    finished_id = insert_session(conn, book_id, ended_at=ENDED_AT)
    insert_session(conn, book_id)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE sessions SET ended_at = NULL WHERE session_id = ?", (finished_id,)
        )


def test_finished_sessions_can_sit_next_to_one_active_session(conn):
    book_id = insert_book(conn)
    insert_session(conn, book_id, ended_at=ENDED_AT)
    insert_session(conn, book_id, ended_at=ENDED_AT)
    insert_session(conn, book_id)
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 3


# --- project root --------------------------------------------------------------


def make_project(root: Path) -> Path:
    (root / "src" / "reading_tracker").mkdir(parents=True)
    (root / "pyproject.toml").write_text("")
    return root


def test_project_root_is_found_from_the_package_location(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # so the working-directory fallback can't help
    assert db.find_project_root() == REPO_ROOT
    assert db.PROJECT_ROOT == REPO_ROOT


def test_find_project_root_walks_up_from_start(tmp_path):
    root = make_project(tmp_path / "repo")
    assert db.find_project_root(root / "src" / "reading_tracker" / "db.py") == root


def test_find_project_root_skips_unrelated_projects(tmp_path, monkeypatch):
    other = tmp_path / "other"
    (other / "pkg").mkdir(parents=True)
    (other / "pyproject.toml").write_text("")
    root = make_project(tmp_path / "repo")
    monkeypatch.chdir(root)
    assert db.find_project_root(other / "pkg" / "module.py") == root


def test_find_project_root_falls_back_to_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert db.find_project_root(tmp_path / "module.py") == tmp_path.resolve()


# --- privacy -------------------------------------------------------------------


@pytest.mark.skipif(
    shutil.which("git") is None or not (REPO_ROOT / ".git").exists(),
    reason="needs git and a git checkout",
)
@pytest.mark.parametrize(
    ("path", "ignored"),
    [
        ("data/raw/reading.db", True),
        ("reading.db", True),
        ("data/scratch.sqlite", True),
        (".env.local", True),
        ("data/demo/demo.db", False),
        ("data/processed/sessions.parquet", False),
    ],
)
def test_private_files_are_gitignored(path, ignored):
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO_ROOT)
    assert result.returncode in (0, 1), "git check-ignore failed"
    assert (result.returncode == 0) is ignored

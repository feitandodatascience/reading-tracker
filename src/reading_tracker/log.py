"""Add books and log reading sessions, enforcing the rules from CLAUDE.md.

Every write in the tracker goes through these functions, so that:

- timestamps are ISO 8601 with a UTC offset (to the second),
- ``ended_at > started_at`` and ``end_pos >= start_pos``,
- positions stay within the book's bounds (pages or 0-100 percent),
- at most one session is active at a time,
- sessions never overlap or end in the future (so minutes are never counted twice),
- text is stripped and stored in Unicode NFC (Vietnamese diacritics compare equal).

Invalid input raises ``ValueError`` with a message that can be shown as is.
"""

import math
import numbers
import operator
import sqlite3
import unicodedata
from datetime import datetime

FORMATS = ("physical", "ebook", "audio")
PROGRESS_UNITS = ("page", "percent")
STATUSES = ("reading", "finished", "abandoned")
DEFAULT_UNIT = {"physical": "page", "ebook": "percent", "audio": "percent"}
MAX_PAGES = 100_000


# --- time helpers -------------------------------------------------------------


def now() -> datetime:
    """Return the current local time as a timezone-aware datetime."""
    return datetime.now().astimezone()


def to_timestamp(moment: datetime) -> str:
    """Format an aware datetime as ISO 8601 with its UTC offset, to the second."""
    if not isinstance(moment, datetime) or moment.utcoffset() is None:
        raise ValueError("Timestamps must be timezone-aware datetimes.")
    return moment.isoformat(timespec="seconds")


def parse_timestamp(text: str) -> datetime:
    """Parse a stored ISO 8601 timestamp back into an aware datetime."""
    moment = datetime.fromisoformat(text)
    if moment.utcoffset() is None:
        raise ValueError(f"Stored timestamp {text!r} has no UTC offset.")
    return moment


def _normalise(moment: datetime) -> datetime:
    """Return ``moment`` exactly as it will be stored: whole seconds, fixed offset.

    Validating the normalised value checks what actually gets written, and turns
    zoneinfo datetimes into fixed offsets so comparisons around DST are correct.
    """
    return parse_timestamp(to_timestamp(moment))


# --- reads --------------------------------------------------------------------


def get_book(conn: sqlite3.Connection, book_id: int) -> dict:
    """Return one book as a dict, or raise ``ValueError`` if it doesn't exist."""
    try:
        book_id = operator.index(book_id)  # also accepts numpy integers
    except TypeError:
        raise ValueError(f"No book with id {book_id!r}.") from None
    row = conn.execute("SELECT * FROM books WHERE book_id = ?", (book_id,)).fetchone()
    if row is None:
        raise ValueError(f"No book with id {book_id}.")
    return dict(row)


def get_active_session(conn: sqlite3.Connection) -> dict | None:
    """Return the active session joined with its book's details, or ``None``."""
    row = conn.execute(
        """
        SELECT s.*, b.title, b.author, b.format, b.progress_unit, b.total_pages
        FROM sessions AS s
        JOIN books AS b USING (book_id)
        WHERE s.ended_at IS NULL
        """
    ).fetchone()
    return dict(row) if row else None


def list_books(conn: sqlite3.Connection) -> list[dict]:
    """Return all books for the tracker's pickers, most relevant first.

    Books being read come first, then finished and abandoned ones. Within each
    group, the most recently read (or added) book comes first. Each dict also
    holds ``last_end_pos``: where the latest finished session of that book ended.
    """
    books = [dict(row) for row in conn.execute("SELECT * FROM books")]
    finished = conn.execute(
        "SELECT book_id, ended_at, end_pos FROM sessions WHERE ended_at IS NOT NULL"
    ).fetchall()

    latest: dict[int, tuple[datetime, float]] = {}
    for row in finished:
        ended = parse_timestamp(row["ended_at"])
        if row["book_id"] not in latest or ended > latest[row["book_id"]][0]:
            latest[row["book_id"]] = (ended, row["end_pos"])

    for book in books:
        last_read, last_end_pos = latest.get(book["book_id"], (None, None))
        added = parse_timestamp(book["added_at"])
        book["last_end_pos"] = last_end_pos
        book["last_touched"] = max(last_read, added) if last_read else added

    return sorted(
        books,
        key=lambda b: (b["status"] != "reading", -b["last_touched"].timestamp()),
    )


# --- validation ---------------------------------------------------------------


def _to_number(value: float, label: str) -> float:
    """Return ``value`` as a finite float; accepts numpy and pandas numbers."""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"{label} must be a number.")
    try:
        number = float(value)
    except OverflowError:
        raise ValueError(f"{label} is too large.") from None
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a number.")
    return number


def _to_position(book: dict, value: float, label: str) -> float:
    """Return ``value`` as a float, checked against the book's bounds."""
    position = _to_number(value, label)
    if book["progress_unit"] == "percent":
        upper, unit = 100, "%"
    else:
        upper, unit = book["total_pages"], " pages"
    if upper is None and position < 0:
        raise ValueError(f"{label} must be 0 or more.")
    if upper is not None and not 0 <= position <= upper:
        raise ValueError(
            f"{label} must be between 0 and {upper}{unit} for '{book['title']}'."
        )
    return position


def _check_not_in_future(moment: datetime, label: str) -> None:
    if moment > now():
        raise ValueError(f"{label} can't be in the future.")


def _check_no_overlap(
    conn: sqlite3.Connection,
    start: datetime,
    end: datetime | None,
    ignore_session_id: int | None = None,
) -> None:
    """Raise if [start, end) overlaps another session; ``end=None`` is open-ended.

    The active session counts as running until further notice. Sessions that only
    touch (one ends exactly when the next starts) don't overlap.
    """
    for row in conn.execute("SELECT session_id, started_at, ended_at FROM sessions"):
        if row["session_id"] == ignore_session_id:
            continue
        other_start = parse_timestamp(row["started_at"])
        other_end = parse_timestamp(row["ended_at"]) if row["ended_at"] else None
        starts_before_other_ends = other_end is None or start < other_end
        other_starts_before_end = end is None or other_start < end
        if starts_before_other_ends and other_starts_before_end:
            raise ValueError(
                f"This overlaps another session (started {other_start:%Y-%m-%d %H:%M})."
            )


def _require_active(
    conn: sqlite3.Connection, session_id: int | None, action: str
) -> dict:
    """Return the active session; if ``session_id`` is given, it must be that one."""
    active = get_active_session(conn)
    if active is None and session_id is None:
        raise ValueError(f"There is no active session to {action}.")
    if active is None or session_id not in (None, active["session_id"]):
        raise ValueError("That session has already ended, maybe in another tab.")
    return active


def _clean_text(text: str | None) -> str | None:
    """Strip and NFC-normalise text; empty or non-text values become ``None``."""
    if not isinstance(text, str):
        return None
    text = unicodedata.normalize("NFC", text).strip()
    return text or None


# --- writes -------------------------------------------------------------------


def add_book(
    conn: sqlite3.Connection,
    title: str,
    *,
    author: str | None = None,
    genre: str | None = None,
    language: str | None = None,
    format: str = "physical",
    progress_unit: str | None = None,
    total_pages: int | None = None,
    status: str = "reading",
    added_at: datetime | None = None,
) -> int:
    """Add a book and return its ``book_id``.

    Parameters
    ----------
    language
        Free text such as ``"English"`` or ``"Vietnamese"``.
    format
        ``"physical"``, ``"ebook"`` or ``"audio"``.
    progress_unit
        ``"page"`` or ``"percent"``. Defaults to pages for physical books and
        percent for ebooks and audiobooks.
    total_pages
        Print-equivalent page count. Required when progress is tracked in pages.
    """
    title = _clean_text(title)
    if title is None:
        raise ValueError("A book needs a title.")
    if format not in FORMATS:
        raise ValueError(f"Format must be one of {', '.join(FORMATS)}.")
    progress_unit = progress_unit or DEFAULT_UNIT[format]
    if progress_unit not in PROGRESS_UNITS:
        raise ValueError(f"Progress unit must be one of {', '.join(PROGRESS_UNITS)}.")
    if format == "audio" and progress_unit == "page":
        raise ValueError("Audiobooks are tracked in percent, not pages.")
    if total_pages is not None:
        pages = _to_number(total_pages, "Total pages")
        if not pages.is_integer() or not 0 < pages <= MAX_PAGES:
            raise ValueError(
                f"Total pages must be a whole number from 1 to {MAX_PAGES:,}."
            )
        total_pages = int(pages)
    if progress_unit == "page" and total_pages is None:
        raise ValueError("Total pages is required when tracking progress in pages.")
    if status not in STATUSES:
        raise ValueError(f"Status must be one of {', '.join(STATUSES)}.")
    added_at = _normalise(added_at or now())

    with conn:
        cursor = conn.execute(
            """
            INSERT INTO books (title, author, genre, language, format,
                               progress_unit, total_pages, added_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                _clean_text(author),
                _clean_text(genre),
                _clean_text(language),
                format,
                progress_unit,
                total_pages,
                to_timestamp(added_at),
                status,
            ),
        )
    return cursor.lastrowid


def start_session(
    conn: sqlite3.Connection,
    book_id: int,
    start_pos: float,
    *,
    started_at: datetime | None = None,
) -> int:
    """Start a reading session now (or at ``started_at``) and return its id."""
    book = get_book(conn, book_id)
    active = get_active_session(conn)
    if active is not None:
        raise ValueError(f"'{active['title']}' is still being read. Stop it first.")
    start_pos = _to_position(book, start_pos, "Start position")
    started_at = _normalise(started_at or now())
    _check_not_in_future(started_at, "Start time")
    _check_no_overlap(conn, started_at, None)

    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO sessions (book_id, started_at, start_pos)"
                " VALUES (?, ?, ?)",
                (book["book_id"], to_timestamp(started_at), start_pos),
            )
    except sqlite3.IntegrityError as error:  # another tab started one meanwhile
        raise ValueError("Another session is already active.") from error
    return cursor.lastrowid


def stop_session(
    conn: sqlite3.Connection,
    end_pos: float,
    *,
    ended_at: datetime | None = None,
    note: str | None = None,
    session_id: int | None = None,
) -> int:
    """Stop the active session at ``end_pos`` and return its id.

    Pass ``session_id`` to make sure the session being stopped is the one the
    user was looking at, not a newer one started elsewhere.
    """
    active = _require_active(conn, session_id, "stop")
    end_pos = _to_position(active, end_pos, "End position")
    if end_pos < active["start_pos"]:
        raise ValueError(
            "End position can't be before the start position"
            f" ({active['start_pos']:g})."
        )
    started_at = parse_timestamp(active["started_at"])
    ended_at = _normalise(ended_at or now())
    if ended_at <= started_at:
        raise ValueError("End time must be after the start time.")
    _check_not_in_future(ended_at, "End time")
    _check_no_overlap(
        conn, started_at, ended_at, ignore_session_id=active["session_id"]
    )

    with conn:
        conn.execute(
            "UPDATE sessions SET ended_at = ?, end_pos = ?, note = ?"
            " WHERE session_id = ?",
            (to_timestamp(ended_at), end_pos, _clean_text(note), active["session_id"]),
        )
    return active["session_id"]


def add_manual_session(
    conn: sqlite3.Connection,
    book_id: int,
    started_at: datetime,
    ended_at: datetime,
    start_pos: float,
    end_pos: float,
    *,
    note: str | None = None,
) -> int:
    """Log a past, already finished session and return its id."""
    book = get_book(conn, book_id)
    started_at = _normalise(started_at)
    ended_at = _normalise(ended_at)
    if ended_at <= started_at:
        raise ValueError("End time must be after the start time.")
    _check_not_in_future(ended_at, "End time")
    start_pos = _to_position(book, start_pos, "Start position")
    end_pos = _to_position(book, end_pos, "End position")
    if end_pos < start_pos:
        raise ValueError("End position can't be before the start position.")
    _check_no_overlap(conn, started_at, ended_at)

    with conn:
        cursor = conn.execute(
            """
            INSERT INTO sessions (book_id, started_at, ended_at, start_pos, end_pos,
                                  note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                book["book_id"],
                to_timestamp(started_at),
                to_timestamp(ended_at),
                start_pos,
                end_pos,
                _clean_text(note),
            ),
        )
    return cursor.lastrowid


def discard_active_session(
    conn: sqlite3.Connection, session_id: int | None = None
) -> None:
    """Delete the active session, for when Start was pressed by mistake.

    Pass ``session_id`` to make sure only the session the user saw is deleted.
    """
    active = _require_active(conn, session_id, "discard")
    with conn:
        conn.execute(
            "DELETE FROM sessions WHERE session_id = ?", (active["session_id"],)
        )


def mark_book_status(conn: sqlite3.Connection, book_id: int, status: str) -> None:
    """Set a book's status to ``"reading"``, ``"finished"`` or ``"abandoned"``."""
    if status not in STATUSES:
        raise ValueError(f"Status must be one of {', '.join(STATUSES)}.")
    book = get_book(conn, book_id)
    with conn:
        conn.execute(
            "UPDATE books SET status = ? WHERE book_id = ?", (status, book["book_id"])
        )

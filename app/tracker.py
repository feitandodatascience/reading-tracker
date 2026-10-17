"""Private reading tracker: start and stop a reading session in a few clicks.

Run it from the repo root, reachable from this computer only:

    uv run streamlit run app/tracker.py --server.address localhost

It writes to data/raw/reading.db, which is gitignored. To try it on a scratch
database first, point READING_TRACKER_DB somewhere else for one run (PowerShell):

    $env:READING_TRACKER_DB = "data/raw/try.db"
    uv run streamlit run app/tracker.py --server.address localhost
    Remove-Item Env:READING_TRACKER_DB
"""

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

from reading_tracker import brand, db, log

DB_PATH = Path(os.environ.get("READING_TRACKER_DB") or db.RAW_DB_PATH)

FORMAT_LABELS = {"physical": "Physical", "ebook": "Ebook", "audio": "Audiobook"}
UNIT_LABELS = {"auto": "Auto", "page": "Pages", "percent": "Percent"}
STATUS_LABELS = {"reading": "Reading", "finished": "Finished", "abandoned": "Abandoned"}
DEFAULT_LANGUAGES = ["English", "Vietnamese"]
LOCAL_ADDRESSES = ("localhost", "127.0.0.1", "::1")

# Make the one action that matters on each screen big enough to hit blind, in
# the brand's single accent (Clay) with Espresso text, as brand.md asks.
BIG = '.st-key-start button, [class*="st-key-stop_"] button'
BIG_BUTTONS_CSS = f"""
<style>
{BIG} {{ min-height: 4.5rem; background: {brand.CLAY}; border-color: {brand.CLAY}; }}
{BIG}:hover {{ background: {brand.CLAY}; border-color: {brand.ESPRESSO}; }}
{BIG} p {{ font-size: 1.4rem; font-weight: 700; color: {brand.ESPRESSO}; }}
</style>
"""


# --- small helpers --------------------------------------------------------------


def format_duration(seconds: float) -> str:
    """Format seconds as '1 hour, 5 minutes, 9 seconds' (zero leading units left out).

    ``45`` -> '45 seconds', ``725`` -> '12 minutes, 5 seconds'.
    """
    minutes, secs = divmod(max(int(seconds), 0), 60)
    hours, minutes = divmod(minutes, 60)
    parts = [(hours, "hour"), (minutes, "minute"), (secs, "second")]
    while len(parts) > 1 and parts[0][0] == 0:
        parts.pop(0)
    return ", ".join(f"{n} {unit}{'' if n == 1 else 's'}" for n, unit in parts)


def book_labels(books: list[dict]) -> dict[int, str]:
    """Map book_id to 'Title by Author', adding the id only to tell twins apart.

    Labels must not change when a book's status changes: Streamlit remembers a
    selectbox choice by its label, so a changed label silently resets the pick.
    """
    labels = {}
    for book in books:
        label = book["title"]
        if book["author"]:
            label += f" by {book['author']}"
        labels[book["book_id"]] = label
    counts = {label: list(labels.values()).count(label) for label in labels.values()}
    return {
        book_id: f"{label} (#{book_id})" if counts[label] > 1 else label
        for book_id, label in labels.items()
    }


def book_picker(books: list[dict], key: str) -> dict:
    """Selectbox over ``books`` (already sorted most relevant first)."""
    by_id = {book["book_id"]: book for book in books}
    labels = book_labels(books)
    book_id = st.selectbox("Book", list(by_id), format_func=labels.get, key=key)
    return by_id[book_id]


def reached_end(book: dict, position: float) -> bool:
    if book["progress_unit"] == "percent":
        return position >= 100
    return book["total_pages"] is not None and position >= book["total_pages"]


def position_input(label: str, book: dict, value: float, key: str) -> float:
    """Number input in the book's unit (whole pages, or percent).

    No min/max on purpose: Streamlit silently keeps the old value when a typed
    number is out of range, while ``log`` rejects it with a clear message.
    """
    if book["progress_unit"] == "percent":
        return st.number_input(
            f"{label} (%)", value=float(value), step=1.0, format="%.1f", key=key
        )
    return st.number_input(f"{label} (page)", value=int(value), step=1, key=key)


def seed_key(prefix: str, book: dict) -> str:
    """Widget key that changes whenever the book's last end position changes.

    Streamlit ignores a new default ``value`` for an existing key, so putting the
    prefill in the key is what keeps "start where you stopped" up to date.
    """
    return f"{prefix}_{book['book_id']}_{book['last_end_pos'] or 0:g}"


def flash(message: str) -> None:
    """Show ``message`` after the next rerun."""
    st.session_state["flash"] = message


def select_next_book(conn: sqlite3.Connection, book_id: int | None = None) -> None:
    """Preselect ``book_id`` (or the top reading book) in the Start picker."""
    if book_id is None:
        reading = [b for b in log.list_books(conn) if b["status"] == "reading"]
        book_id = reading[0]["book_id"] if reading else None
    st.session_state["select_book"] = book_id


# --- screens ---------------------------------------------------------------------


@st.fragment(run_every="1s")
def elapsed_timer(started: datetime) -> None:
    elapsed = (log.now() - started).total_seconds()
    st.metric(
        "Reading for", format_duration(elapsed), help=f"Started at {started:%H:%M:%S}"
    )


def render_active_session(conn: sqlite3.Connection, session: dict) -> None:
    session_id = session["session_id"]
    st.subheader(session["title"])
    if session["author"]:
        st.caption(session["author"])
    elapsed_timer(log.parse_timestamp(session["started_at"]))

    end_pos = position_input(
        "Stopped at", session, value=session["start_pos"], key=f"end_pos_{session_id}"
    )
    note = st.text_input("Note (optional)", key=f"note_{session_id}")

    # Keys include the session id, so a click in a stale tab can't stop or
    # discard a newer session started somewhere else.
    if st.button("Stop", key=f"stop_{session_id}", type="primary", width="stretch"):
        try:
            log.stop_session(conn, end_pos, note=note, session_id=session_id)
        except ValueError as error:
            st.error(str(error))
        else:
            elapsed = log.now() - log.parse_timestamp(session["started_at"])
            flash(f"Logged {format_duration(elapsed.total_seconds())} of reading.")
            if reached_end(session, end_pos):
                st.session_state["finished_prompt"] = session["book_id"]
            st.rerun()

    with st.popover("Discard session", type="tertiary"):
        st.write("Delete this session without logging it?")
        if st.button("Yes, discard", key=f"discard_{session_id}"):
            try:
                log.discard_active_session(conn, session_id=session_id)
            except ValueError as error:
                st.error(str(error))
            else:
                flash("Session discarded.")
                st.rerun()


def render_start(conn: sqlite3.Connection, books: list[dict]) -> None:
    if not books:
        st.info("Add your first book below to start tracking.")
        return

    if "select_book" in st.session_state:  # set by add book or a status change
        if (book_id := st.session_state.pop("select_book")) is None:
            st.session_state.pop("start_book", None)
        else:
            st.session_state["start_book"] = book_id
    book = book_picker(books, key="start_book")
    if book["status"] != "reading":
        st.caption(f"This book is marked {book['status']}.")
    start_pos = position_input(
        "Starting at",
        book,
        value=book["last_end_pos"] or 0,
        key=seed_key("start", book),
    )

    if st.button("Start", key="start", type="primary", width="stretch"):
        try:
            log.start_session(conn, book["book_id"], start_pos)
        except ValueError as error:
            st.error(str(error))
        else:
            st.rerun()


def render_finished_prompt(conn: sqlite3.Connection) -> None:
    book = log.get_book(conn, st.session_state["finished_prompt"])
    st.success(f"You reached the end of *{book['title']}*. Mark it as finished?")
    yes, no = st.columns(2)
    if yes.button("Mark as finished", key="mark_finished", width="stretch"):
        log.mark_book_status(conn, book["book_id"], "finished")
        del st.session_state["finished_prompt"]
        select_next_book(conn)
        flash(f"Marked *{book['title']}* as finished.")
        st.rerun()
    if no.button("Not yet", key="not_finished", width="stretch"):
        del st.session_state["finished_prompt"]
        st.rerun()


# --- expanders -------------------------------------------------------------------


def render_add_book(conn: sqlite3.Connection, books: list[dict]) -> None:
    # Bumping the form number after a successful add gives a fresh, empty form,
    # while a failed add keeps what was typed.
    n = st.session_state.setdefault("add_book_form", 0)
    genres = sorted({book["genre"] for book in books if book["genre"]})
    languages = list(
        dict.fromkeys(
            DEFAULT_LANGUAGES + sorted({b["language"] for b in books if b["language"]})
        )
    )
    newest = max(books, key=lambda b: log.parse_timestamp(b["added_at"]), default=None)
    last_language = newest["language"] if newest else None

    with st.expander("Add book", expanded=not books), st.form(f"add_book_{n}"):
        title = st.text_input("Title", key=f"title_{n}")
        author = st.text_input("Author", key=f"author_{n}")
        genre_col, language_col = st.columns(2)
        genre = genre_col.selectbox(
            "Genre",
            genres,
            index=None,
            accept_new_options=True,
            placeholder="Pick or type a genre",
            key=f"genre_{n}",
        )
        language = language_col.selectbox(
            "Language",
            languages,
            index=languages.index(last_language) if last_language in languages else 0,
            accept_new_options=True,
            key=f"language_{n}",
        )
        format_col, unit_col = st.columns(2)
        with format_col:
            book_format = st.segmented_control(
                "Format",
                list(FORMAT_LABELS),
                default="physical",
                required=True,
                format_func=FORMAT_LABELS.get,
                key=f"format_{n}",
            )
        with unit_col:
            unit = st.segmented_control(
                "Track progress in",
                list(UNIT_LABELS),
                default="auto",
                required=True,
                format_func=UNIT_LABELS.get,
                help="Auto: pages for physical books, percent for ebooks and audio.",
                key=f"unit_{n}",
            )
        total_pages = st.number_input(
            "Total pages (print edition)",
            min_value=1,
            value=None,
            step=1,
            placeholder="Needed when tracking pages",
            key=f"pages_{n}",
        )
        submitted = st.form_submit_button("Add book", key=f"add_{n}")

    if submitted:
        try:
            book_id = log.add_book(
                conn,
                title,
                author=author,
                genre=genre,
                language=language,
                format=book_format,
                progress_unit=None if unit == "auto" else unit,
                total_pages=total_pages,
            )
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state["add_book_form"] = n + 1
            st.session_state["select_book"] = book_id
            flash(f"Added *{log.get_book(conn, book_id)['title']}*.")
            st.rerun()


def render_past_session(conn: sqlite3.Connection, books: list[dict]) -> None:
    with st.expander("Log a past session"):
        if not books:
            st.caption("Add a book first.")
            return
        book = book_picker(books, key="past_book")
        n = st.session_state.setdefault("past_form", 0)  # bumped after a log

        when_col, minutes_col = st.columns(2)
        started = when_col.datetime_input(
            "Started",
            value=datetime.now().replace(second=0, microsecond=0) - timedelta(hours=1),
            max_value=datetime.now(),
            step=timedelta(minutes=5),
            format="YYYY-MM-DD",
            key=f"past_started_{n}",
        )
        minutes = minutes_col.number_input(
            "Minutes read",
            min_value=1,
            max_value=24 * 60,
            value=30,
            step=5,
            key=f"past_minutes_{n}",
        )
        from_col, to_col = st.columns(2)
        last = book["last_end_pos"] or 0
        with from_col:
            start_pos = position_input(
                "From", book, value=last, key=seed_key(f"past_from_{n}", book)
            )
        with to_col:
            end_pos = position_input(
                "To", book, value=last, key=seed_key(f"past_to_{n}", book)
            )
        note = st.text_input("Note (optional)", key=f"past_note_{n}")

        if st.button("Log session", key="log_past"):
            started_at = started.astimezone()  # the widget returns local, naive time
            ended_at = (started_at + timedelta(minutes=minutes)).astimezone()
            try:
                log.add_manual_session(
                    conn,
                    book["book_id"],
                    started_at,
                    ended_at,
                    start_pos,
                    end_pos,
                    note=note,
                )
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state["past_form"] = n + 1
                flash(f"Logged {format_duration(minutes * 60)} of *{book['title']}*.")
                st.rerun()


def render_book_status(conn: sqlite3.Connection, books: list[dict]) -> None:
    with st.expander("Finish or abandon a book"):
        if not books:
            st.caption("Add a book first.")
            return
        book = book_picker(books, key="status_book")
        status = st.segmented_control(
            "Status",
            list(STATUS_LABELS),
            default=book["status"],
            required=True,
            format_func=STATUS_LABELS.get,
            key=f"status_{book['book_id']}_{book['status']}",
        )
        if st.button("Update status", key="update_status"):
            log.mark_book_status(conn, book["book_id"], status)
            select_next_book(conn, book["book_id"] if status == "reading" else None)
            flash(f"*{book['title']}* is now {status}.")
            st.rerun()


# --- page ------------------------------------------------------------------------


def render_safety_notes() -> None:
    """Warn when the private tracker is exposed or writing to a test database."""
    if st.get_option("server.address") not in LOCAL_ADDRESSES:
        st.warning(
            "This tracker is reachable from your network. Restart it with"
            " `--server.address localhost` to keep it private."
        )
    path = DB_PATH.resolve()
    if path.is_relative_to(db.PROJECT_ROOT):
        shown = path.relative_to(db.PROJECT_ROOT).as_posix()
    else:
        shown = f"{path.name} (custom location)"
    if path != db.RAW_DB_PATH.resolve():
        st.warning(f"Logging to a test database: `{shown}` (READING_TRACKER_DB).")
    else:
        st.caption(f"Logging to `{shown}`")


def main() -> None:
    st.set_page_config(page_title="Reading tracker", layout="centered")
    st.html(BIG_BUTTONS_CSS)
    st.title("Reading tracker")
    render_safety_notes()

    with closing(db.connect(DB_PATH)) as conn:
        if message := st.session_state.pop("flash", None):
            st.success(message)
        if "finished_prompt" in st.session_state:
            render_finished_prompt(conn)

        session = log.get_active_session(conn)
        books = log.list_books(conn)
        if session:
            # A book added mid-session shouldn't hijack the picker after Stop.
            st.session_state.pop("select_book", None)
            render_active_session(conn, session)
        else:
            render_start(conn, books)

        st.divider()
        render_add_book(conn, books)
        render_past_session(conn, books)
        render_book_status(conn, books)


main()

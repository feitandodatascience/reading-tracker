"""Tests for book and session logging, its validation, and the one-active rule."""

import math
import re
import unicodedata
from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from reading_tracker import db, log

TZ = timezone(timedelta(hours=7))
EVENING = datetime(2026, 1, 5, 20, 0, tzinfo=TZ)
ISO_WITH_OFFSET = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    yield connection
    connection.close()


@pytest.fixture
def book_id(conn):
    """A 300-page physical book."""
    return log.add_book(conn, "Dune", author="Frank Herbert", total_pages=300)


@pytest.fixture
def ebook_id(conn):
    """An ebook tracked in percent."""
    return log.add_book(conn, "Piranesi", format="ebook", total_pages=270)


def at(minutes: float) -> datetime:
    """EVENING plus ``minutes``."""
    return EVENING + timedelta(minutes=minutes)


def session_rows(conn):
    return [dict(row) for row in conn.execute("SELECT * FROM sessions")]


# --- timestamps --------------------------------------------------------------


def test_to_timestamp_keeps_offset_and_drops_microseconds():
    moment = datetime(2026, 1, 5, 20, 0, 7, 123456, tzinfo=TZ)
    assert log.to_timestamp(moment) == "2026-01-05T20:00:07+07:00"


@pytest.mark.parametrize("moment", [datetime(2026, 1, 5, 20, 0), "2026-01-05", None])
def test_to_timestamp_rejects_naive_or_non_datetimes(moment):
    with pytest.raises(ValueError, match="timezone-aware"):
        log.to_timestamp(moment)


def test_now_is_timezone_aware():
    assert log.now().utcoffset() is not None


def test_parse_timestamp_names_a_stored_value_without_offset():
    with pytest.raises(ValueError, match="'2026-01-04 20:00:00' has no UTC offset"):
        log.parse_timestamp("2026-01-04 20:00:00")


# --- add_book ------------------------------------------------------------------


def test_add_book_stores_cleaned_values(conn):
    new_id = log.add_book(
        conn,
        "  Dune ",
        author=" Frank Herbert ",
        genre=" ",
        language=" English ",
        total_pages=412,
    )
    book = log.get_book(conn, new_id)
    assert book["title"] == "Dune"
    assert book["author"] == "Frank Herbert"
    assert book["genre"] is None
    assert book["language"] == "English"
    assert book["status"] == "reading"
    assert ISO_WITH_OFFSET.match(book["added_at"])


def test_add_book_keeps_given_added_at(conn):
    new_id = log.add_book(conn, "Dune", total_pages=412, added_at=at(100.5))
    assert log.get_book(conn, new_id)["added_at"] == "2026-01-05T21:40:30+07:00"


def test_add_book_round_trips_vietnamese_text(conn):
    new_id = log.add_book(
        conn,
        "Tôi thấy hoa vàng trên cỏ xanh",
        author="Nguyễn Nhật Ánh",
        genre="Tiểu thuyết",
        language="Vietnamese",
        total_pages=378,
    )
    book = log.get_book(conn, new_id)
    assert book["title"] == "Tôi thấy hoa vàng trên cỏ xanh"
    assert book["author"] == "Nguyễn Nhật Ánh"
    assert book["genre"] == "Tiểu thuyết"


def test_add_book_stores_text_in_nfc_so_keyboards_agree(conn):
    decomposed = unicodedata.normalize("NFD", "Nguyễn Nhật Ánh")
    assert decomposed != "Nguyễn Nhật Ánh"
    new_id = log.add_book(conn, "Mắt biếc", author=decomposed, total_pages=300)
    assert log.get_book(conn, new_id)["author"] == "Nguyễn Nhật Ánh"


@pytest.mark.parametrize(
    ("book_format", "expected_unit"),
    [("physical", "page"), ("ebook", "percent"), ("audio", "percent")],
)
def test_add_book_defaults_progress_unit_by_format(conn, book_format, expected_unit):
    new_id = log.add_book(conn, "Book", format=book_format, total_pages=100)
    assert log.get_book(conn, new_id)["progress_unit"] == expected_unit


def test_add_book_allows_ebook_tracked_in_pages(conn):
    new_id = log.add_book(
        conn, "Book", format="ebook", progress_unit="page", total_pages=100
    )
    assert log.get_book(conn, new_id)["progress_unit"] == "page"


def test_add_book_allows_percent_book_without_page_count(conn):
    new_id = log.add_book(conn, "Book", format="audio")
    assert log.get_book(conn, new_id)["total_pages"] is None


@pytest.mark.parametrize("pages", [300.0, np.int64(300), np.float64(300.0)])
def test_add_book_accepts_whole_numbers_of_any_numeric_type(conn, pages):
    new_id = log.add_book(conn, "Dune", total_pages=pages)
    stored = conn.execute(
        "SELECT total_pages, typeof(total_pages) AS kind FROM books WHERE book_id = ?",
        (new_id,),
    ).fetchone()
    assert (stored["total_pages"], stored["kind"]) == (300, "integer")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"title": "   \n"}, "needs a title"),
        ({"title": None}, "needs a title"),
        ({"format": "comic"}, "Format must be"),
        ({"progress_unit": "chapter"}, "Progress unit must be"),
        ({"format": "audio", "progress_unit": "page"}, "Audiobooks"),
        ({"total_pages": None}, "required when tracking progress in pages"),
        ({"total_pages": 0}, "whole number from 1"),
        ({"total_pages": -5}, "whole number from 1"),
        ({"total_pages": 12.5}, "whole number from 1"),
        ({"total_pages": 10**6}, "whole number from 1"),
        ({"total_pages": True}, "Total pages must be a number"),
        ({"total_pages": math.inf}, "Total pages must be a number"),
        ({"total_pages": math.nan}, "Total pages must be a number"),
        ({"total_pages": "300"}, "Total pages must be a number"),
        ({"status": "paused"}, "Status must be"),
    ],
)
def test_add_book_rejects_invalid_input(conn, kwargs, message):
    values = {"title": "Dune", "total_pages": 300, **kwargs}
    with pytest.raises(ValueError, match=message):
        log.add_book(conn, values.pop("title"), **values)
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0


# --- start_session and the one-active-session rule -------------------------------


def test_start_session_creates_the_active_session(conn, book_id):
    session_id = log.start_session(conn, book_id, 12, started_at=EVENING)
    active = log.get_active_session(conn)
    assert active["session_id"] == session_id
    assert active["title"] == "Dune"
    assert active["start_pos"] == 12
    assert active["started_at"] == "2026-01-05T20:00:00+07:00"
    assert active["ended_at"] is None


def test_get_active_session_is_none_without_one(conn, book_id):
    assert log.get_active_session(conn) is None


def test_second_active_session_is_rejected(conn, book_id, ebook_id):
    log.start_session(conn, book_id, 0, started_at=EVENING)
    with pytest.raises(ValueError, match="'Dune' is still being read"):
        log.start_session(conn, ebook_id, 0)
    assert len(session_rows(conn)) == 1


def test_racing_second_start_is_reported_as_validation_error(
    conn, book_id, monkeypatch
):
    log.start_session(conn, book_id, 0, started_at=EVENING)
    # Simulate another tab that checked for an active session just before ours.
    monkeypatch.setattr(log, "get_active_session", lambda conn: None)
    monkeypatch.setattr(log, "_check_no_overlap", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="already active"):
        log.start_session(conn, book_id, 0)


def test_start_session_after_stop_is_allowed(conn, book_id):
    log.start_session(conn, book_id, 0, started_at=at(0))
    log.stop_session(conn, 20, ended_at=at(30))
    log.start_session(conn, book_id, 20, started_at=at(60))
    assert log.get_active_session(conn)["start_pos"] == 20


@pytest.mark.parametrize("bad_id", [42, "1", None])
def test_start_session_rejects_unknown_book(conn, book_id, bad_id):
    with pytest.raises(ValueError, match="No book with id"):
        log.start_session(conn, bad_id, 0)


def test_start_session_accepts_numpy_ids_and_positions(conn, book_id):
    log.start_session(conn, np.int64(book_id), np.float64(12.5), started_at=EVENING)
    assert log.get_active_session(conn)["start_pos"] == 12.5


@pytest.mark.parametrize(
    "position", [-1, 301, math.nan, math.inf, "12", None, True, 10**400]
)
def test_start_session_rejects_positions_outside_page_bounds(conn, book_id, position):
    with pytest.raises(ValueError, match="Start position"):
        log.start_session(conn, book_id, position, started_at=EVENING)


@pytest.mark.parametrize("position", [0, 300])
def test_start_session_accepts_page_bounds(conn, book_id, position):
    log.start_session(conn, book_id, position, started_at=EVENING)


def test_percent_book_positions_are_capped_at_100(conn, ebook_id):
    with pytest.raises(ValueError, match="between 0 and 100%"):
        log.start_session(conn, ebook_id, 100.5, started_at=EVENING)
    log.start_session(conn, ebook_id, 99.5, started_at=EVENING)


def test_page_book_without_page_count_only_rejects_negative_positions(conn):
    with conn:  # a legacy row that add_book would refuse
        conn.execute(
            "INSERT INTO books (title, progress_unit, added_at)"
            " VALUES ('Legacy', 'page', '2026-01-01T00:00:00+07:00')"
        )
    with pytest.raises(ValueError, match="must be 0 or more"):
        log.start_session(conn, 1, -1, started_at=EVENING)
    log.start_session(conn, 1, 5000, started_at=EVENING)


def test_start_session_rejects_naive_start_time(conn, book_id):
    with pytest.raises(ValueError, match="timezone-aware"):
        log.start_session(conn, book_id, 0, started_at=datetime(2026, 1, 5, 20, 0))


def test_start_session_rejects_future_start_time(conn, book_id):
    with pytest.raises(ValueError, match="future"):
        log.start_session(conn, book_id, 0, started_at=log.now() + timedelta(hours=1))


def test_start_session_rejects_start_inside_a_finished_session(conn, book_id):
    log.add_manual_session(conn, book_id, at(0), at(60), 0, 20)
    with pytest.raises(ValueError, match="overlaps"):
        log.start_session(conn, book_id, 20, started_at=at(30))


def test_start_session_rejects_start_before_a_later_finished_session(conn, book_id):
    log.add_manual_session(conn, book_id, at(60), at(90), 0, 20)
    with pytest.raises(ValueError, match="overlaps"):
        log.start_session(conn, book_id, 0, started_at=at(0))


# --- stop_session ------------------------------------------------------------------


def test_stop_session_records_end(conn, book_id):
    session_id = log.start_session(conn, book_id, 10, started_at=at(0))
    assert log.stop_session(conn, 42, ended_at=at(45), note="  great chapter ") == (
        session_id
    )
    (row,) = session_rows(conn)
    assert row["ended_at"] == "2026-01-05T20:45:00+07:00"
    assert row["end_pos"] == 42
    assert row["note"] == "great chapter"
    assert log.get_active_session(conn) is None


@pytest.mark.parametrize("note", ["   ", "", None, math.nan])
def test_stop_session_stores_empty_note_as_null(conn, book_id, note):
    log.start_session(conn, book_id, 10, started_at=at(0))
    log.stop_session(conn, 12, ended_at=at(5), note=note)
    assert session_rows(conn)[0]["note"] is None


def test_stop_session_defaults_to_now(conn, book_id):
    log.start_session(conn, book_id, 10, started_at=log.now() - timedelta(minutes=5))
    log.stop_session(conn, 15)
    ended = log.parse_timestamp(session_rows(conn)[0]["ended_at"])
    assert abs((log.now() - ended).total_seconds()) < 5
    assert ISO_WITH_OFFSET.match(session_rows(conn)[0]["ended_at"])


def test_stop_session_without_active_session_fails(conn, book_id):
    with pytest.raises(ValueError, match="no active session"):
        log.stop_session(conn, 10)


def test_stop_session_checks_it_stops_the_session_the_user_saw(conn, book_id):
    first = log.start_session(conn, book_id, 10, started_at=at(0))
    log.stop_session(conn, 20, ended_at=at(30), session_id=first)
    log.start_session(conn, book_id, 20, started_at=at(60))  # e.g. in another tab
    with pytest.raises(ValueError, match="already ended"):
        log.stop_session(conn, 25, ended_at=at(90), session_id=first)
    assert log.get_active_session(conn)["start_pos"] == 20


def test_stop_session_allows_zero_page_session(conn, book_id):
    log.start_session(conn, book_id, 10, started_at=at(0))
    log.stop_session(conn, 10, ended_at=at(15))
    assert session_rows(conn)[0]["end_pos"] == 10


def test_stop_session_rejects_end_before_start_position(conn, book_id):
    log.start_session(conn, book_id, 10, started_at=at(0))
    with pytest.raises(ValueError, match="before the start position"):
        log.stop_session(conn, 9, ended_at=at(15))
    assert log.get_active_session(conn) is not None


def test_stop_session_rejects_position_past_last_page(conn, book_id):
    log.start_session(conn, book_id, 10, started_at=at(0))
    with pytest.raises(ValueError, match="between 0 and 300 pages"):
        log.stop_session(conn, 301, ended_at=at(15))


@pytest.mark.parametrize("minutes", [0, -10, 0.5 / 60])
def test_stop_session_rejects_end_not_after_start(conn, book_id, minutes):
    log.start_session(conn, book_id, 10, started_at=at(0))
    with pytest.raises(ValueError, match="after the start time"):
        log.stop_session(conn, 12, ended_at=at(minutes))
    assert log.get_active_session(conn) is not None


def test_stop_session_rejects_future_end(conn, book_id):
    log.start_session(conn, book_id, 10, started_at=log.now() - timedelta(minutes=5))
    with pytest.raises(ValueError, match="future"):
        log.stop_session(conn, 12, ended_at=log.now() + timedelta(hours=1))


def test_stop_session_rejects_naive_end(conn, book_id):
    log.start_session(conn, book_id, 10, started_at=at(0))
    with pytest.raises(ValueError, match="timezone-aware"):
        log.stop_session(conn, 12, ended_at=datetime(2026, 1, 5, 21, 0))


def test_stop_session_compares_times_across_offsets(conn, book_id):
    log.start_session(conn, book_id, 10, started_at=at(0))  # 13:00 UTC
    one_hour_earlier_in_utc = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="after the start time"):
        log.stop_session(conn, 12, ended_at=one_hour_earlier_in_utc)


# --- add_manual_session ------------------------------------------------------------


def test_add_manual_session_stores_a_finished_session(conn, book_id):
    session_id = log.add_manual_session(
        conn, book_id, at(0), at(40), 5, 25, note="  on the train "
    )
    (row,) = session_rows(conn)
    assert row["session_id"] == session_id
    assert row["started_at"] == "2026-01-05T20:00:00+07:00"
    assert row["ended_at"] == "2026-01-05T20:40:00+07:00"
    assert (row["start_pos"], row["end_pos"], row["note"]) == (5, 25, "on the train")


def test_add_manual_session_stores_blank_note_as_null(conn, book_id):
    log.add_manual_session(conn, book_id, at(0), at(40), 5, 25, note="  ")
    assert session_rows(conn)[0]["note"] is None


def test_add_manual_session_allows_spanning_midnight(conn, book_id):
    log.add_manual_session(conn, book_id, at(210), at(270), 0, 30)  # 23:30 -> 00:30
    assert session_rows(conn)[0]["ended_at"] == "2026-01-06T00:30:00+07:00"


@pytest.mark.parametrize(
    ("start", "end", "start_pos", "end_pos", "message"),
    [
        (at(30), at(30), 0, 10, "after the start time"),
        (at(30), at(0), 0, 10, "after the start time"),
        (at(0.1 / 60), at(0.9 / 60), 0, 10, "after the start time"),  # same second
        (at(0), at(30), 20, 10, "before the start position"),
        (at(0), at(30), 0, 301, "End position"),
        (at(0), at(30), -1, 10, "Start position"),
    ],
)
def test_add_manual_session_rejects_invalid_sessions(
    conn, book_id, start, end, start_pos, end_pos, message
):
    with pytest.raises(ValueError, match=message):
        log.add_manual_session(conn, book_id, start, end, start_pos, end_pos)
    assert session_rows(conn) == []


def test_add_manual_session_rejects_future_end(conn, book_id):
    with pytest.raises(ValueError, match="future"):
        log.add_manual_session(
            conn, book_id, log.now(), log.now() + timedelta(hours=1), 0, 10
        )


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (datetime(2026, 1, 5, 20), datetime(2026, 1, 5, 21)),
        (datetime(2026, 1, 5, 20), at(60)),
        (at(0), datetime(2026, 1, 5, 21)),
    ],
)
def test_add_manual_session_rejects_naive_times(conn, book_id, start, end):
    with pytest.raises(ValueError, match="timezone-aware"):
        log.add_manual_session(conn, book_id, start, end, 0, 10)


def test_add_manual_session_rejects_unknown_book(conn):
    with pytest.raises(ValueError, match="No book"):
        log.add_manual_session(conn, 42, at(0), at(30), 0, 10)


def test_add_manual_session_compares_real_instants_across_dst(conn, book_id):
    paris = ZoneInfo("Europe/Paris")  # clocks go back at 03:00 on 2025-10-26
    first_0245 = datetime(2025, 10, 26, 2, 45, tzinfo=paris)  # 00:45 UTC
    second_0215 = datetime(2025, 10, 26, 2, 15, fold=1, tzinfo=paris)  # 01:15 UTC

    # 02:45 (summer time) -> 02:15 (winter time) is a real 30-minute session.
    log.add_manual_session(conn, book_id, first_0245, second_0215, 0, 10)
    assert session_rows(conn)[0]["started_at"] == "2025-10-26T02:45:00+02:00"
    assert session_rows(conn)[0]["ended_at"] == "2025-10-26T02:15:00+01:00"
    # 02:15 (winter) -> 02:45 (summer) would end before it starts.
    with pytest.raises(ValueError, match="after the start time"):
        log.add_manual_session(conn, book_id, second_0215, first_0245, 10, 20)


@pytest.mark.parametrize(
    ("start", "end"),
    [(at(30), at(90)), (at(-30), at(30)), (at(10), at(20)), (at(-10), at(70))],
)
def test_add_manual_session_rejects_overlap(conn, book_id, start, end):
    log.add_manual_session(conn, book_id, at(0), at(60), 0, 20)
    with pytest.raises(ValueError, match="overlaps"):
        log.add_manual_session(conn, book_id, start, end, 20, 30)


def test_add_manual_session_allows_touching_sessions(conn, book_id):
    log.add_manual_session(conn, book_id, at(0), at(60), 0, 20)
    log.add_manual_session(conn, book_id, at(60), at(90), 20, 30)
    log.add_manual_session(conn, book_id, at(-30), at(0), 0, 0)
    assert len(session_rows(conn)) == 3


def test_add_manual_session_detects_overlap_across_offsets(conn, book_id):
    log.add_manual_session(conn, book_id, at(0), at(60), 0, 20)  # 13:00-14:00 UTC
    paris = timezone(timedelta(hours=1))
    with pytest.raises(ValueError, match="overlaps"):
        log.add_manual_session(
            conn,
            book_id,
            datetime(2026, 1, 5, 14, 30, tzinfo=paris),  # 13:30 UTC
            datetime(2026, 1, 5, 15, 30, tzinfo=paris),
            20,
            30,
        )


def test_add_manual_session_cannot_overlap_the_active_session(conn, book_id):
    log.start_session(conn, book_id, 20, started_at=at(60))
    with pytest.raises(ValueError, match="overlaps"):
        log.add_manual_session(conn, book_id, at(30), at(90), 0, 20)
    log.add_manual_session(conn, book_id, at(0), at(60), 0, 20)
    assert len(session_rows(conn)) == 2


# --- discard and status ------------------------------------------------------------


def test_discard_active_session_keeps_finished_ones(conn, book_id):
    log.add_manual_session(conn, book_id, at(0), at(30), 0, 10)
    log.start_session(conn, book_id, 10, started_at=at(60))
    log.discard_active_session(conn)
    assert log.get_active_session(conn) is None
    assert len(session_rows(conn)) == 1


def test_discard_without_active_session_fails(conn):
    with pytest.raises(ValueError, match="no active session"):
        log.discard_active_session(conn)


def test_discard_only_deletes_the_session_the_user_saw(conn, book_id):
    first = log.start_session(conn, book_id, 10, started_at=at(0))
    log.stop_session(conn, 20, ended_at=at(30))
    log.start_session(conn, book_id, 20, started_at=at(60))  # e.g. in another tab
    with pytest.raises(ValueError, match="already ended"):
        log.discard_active_session(conn, session_id=first)
    assert log.get_active_session(conn) is not None


@pytest.mark.parametrize("status", ["finished", "abandoned", "reading"])
def test_mark_book_status_updates_status(conn, book_id, status):
    log.mark_book_status(conn, book_id, status)
    assert log.get_book(conn, book_id)["status"] == status


def test_mark_book_status_rejects_unknown_status_and_book(conn, book_id):
    with pytest.raises(ValueError, match="Status must be"):
        log.mark_book_status(conn, book_id, "paused")
    with pytest.raises(ValueError, match="No book"):
        log.mark_book_status(conn, 42, "finished")
    assert log.get_book(conn, book_id)["status"] == "reading"


# --- list_books ----------------------------------------------------------------------


def titles(conn) -> list[str]:
    return [book["title"] for book in log.list_books(conn)]


def test_list_books_puts_reading_books_first(conn):
    done = log.add_book(conn, "Done", total_pages=100, added_at=at(-60))
    log.add_book(conn, "Reading", total_pages=100, added_at=at(-600))
    log.mark_book_status(conn, done, "finished")
    assert titles(conn) == ["Reading", "Done"]


def test_list_books_orders_by_last_read_or_added_not_insertion(conn):
    first = log.add_book(conn, "Added long ago", total_pages=100, added_at=at(-600))
    log.add_book(conn, "Added recently", total_pages=100, added_at=at(-60))
    assert titles(conn) == ["Added recently", "Added long ago"]

    log.add_manual_session(conn, first, at(0), at(30), 0, 10)
    assert titles(conn) == ["Added long ago", "Added recently"]


def test_list_books_last_end_pos_comes_from_latest_session_in_time(conn, book_id):
    log.add_manual_session(conn, book_id, at(120), at(150), 40, 60)
    log.add_manual_session(conn, book_id, at(0), at(30), 0, 40)  # logged later
    (book,) = log.list_books(conn)
    assert book["last_end_pos"] == 60


def test_list_books_ignores_the_active_session_for_last_end_pos(conn, book_id):
    log.add_manual_session(conn, book_id, at(0), at(30), 0, 40)
    log.start_session(conn, book_id, 40, started_at=at(60))
    assert log.list_books(conn)[0]["last_end_pos"] == 40


def test_list_books_new_book_has_no_last_end_pos(conn, book_id):
    assert log.list_books(conn)[0]["last_end_pos"] is None

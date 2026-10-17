"""Click through the tracker page with Streamlit's AppTest on a temp database."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from reading_tracker import db, log

TRACKER = Path(__file__).resolve().parents[1] / "app" / "tracker.py"


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "tracker.db"
    monkeypatch.setenv("READING_TRACKER_DB", str(path))
    return path


def open_tracker() -> AppTest:
    app = AppTest.from_file(str(TRACKER), default_timeout=30)
    app.run()
    assert not app.exception
    return app


@pytest.fixture
def app(db_path):
    return open_tracker()


@pytest.fixture
def clock(monkeypatch):
    """Fake ``log.now()`` that only moves when told, so sessions last minutes.

    Returns a function: ``clock(minutes=10)`` moves time forward.
    """
    current = [log.now().replace(microsecond=0) - timedelta(hours=3)]
    monkeypatch.setattr(log, "now", lambda: current[0])

    def advance(minutes: int) -> None:
        current[0] += timedelta(minutes=minutes)

    return advance


def add_book(app: AppTest, title: str, pages: int | None = 412, **choices) -> None:
    """Fill in and submit the Add book form (``choices`` maps widget to value)."""
    n = app.session_state["add_book_form"]
    app.text_input(key=f"title_{n}").input(title)
    if pages is not None:
        app.number_input(key=f"pages_{n}").set_value(pages)
    for widget, value in choices.items():
        if widget in ("author",):
            app.text_input(key=f"{widget}_{n}").input(value)
        elif widget in ("language", "genre"):
            app.selectbox(key=f"{widget}_{n}").set_value(value)
        else:
            app.button_group(key=f"{widget}_{n}").set_value(value)
    app.button(key=f"add_{n}").click().run()
    assert not app.exception


def query(db_path: Path, sql: str) -> list[dict]:
    conn = db.connect(db_path)
    try:
        return [dict(row) for row in conn.execute(sql)]
    finally:
        conn.close()


def start_in_the_past(db_path: Path, book_id: int, start_pos: float, minutes: int):
    """Start a session ``minutes`` ago, so stopping it now has a real duration."""
    conn = db.connect(db_path)
    try:
        started = log.now() - timedelta(minutes=minutes)
        return log.start_session(conn, book_id, start_pos, started_at=started)
    finally:
        conn.close()


def stop(app: AppTest, session_id: int, end_pos: float, note: str = "") -> None:
    app.number_input(key=f"end_pos_{session_id}").set_value(end_pos)
    if note:
        app.text_input(key=f"note_{session_id}").input(note)
    app.button(key=f"stop_{session_id}").click().run()
    assert not app.exception


def successes(app: AppTest) -> list[str]:
    return [element.value for element in app.success]


# --- first run and adding books ---------------------------------------------------


def test_empty_database_asks_for_a_first_book(app):
    assert "Add your first book" in app.info[0].value
    assert "start" not in {button.key for button in app.button}


def test_test_database_is_flagged(app):
    assert any("test database" in w.value for w in app.warning)


def test_adding_a_book_preselects_it_and_resets_the_form(app, db_path):
    add_book(app, "Dune")
    add_book(app, "Emma", pages=474)
    assert successes(app) == ["Added *Emma*."]
    assert app.selectbox(key="start_book").value == 2
    assert app.text_input(key="title_2").value == ""
    assert query(db_path, "SELECT title, progress_unit FROM books") == [
        {"title": "Dune", "progress_unit": "page"},
        {"title": "Emma", "progress_unit": "page"},
    ]


def test_flash_message_disappears_on_the_next_rerun(app):
    add_book(app, "Dune")
    assert successes(app) == ["Added *Dune*."]
    app.run()
    assert successes(app) == []


def test_add_book_error_is_shown_and_keeps_the_form(app, db_path):
    add_book(app, "Dune", pages=None)  # physical books need a page count
    assert "Total pages is required" in app.error[0].value
    assert app.text_input(key="title_0").value == "Dune"
    assert query(db_path, "SELECT * FROM books") == []


def test_add_vietnamese_ebook_with_language_and_format(app, db_path):
    add_book(
        app,
        "Tôi thấy hoa vàng trên cỏ xanh",
        pages=None,
        author="Nguyễn Nhật Ánh",
        language="Vietnamese",
        format="ebook",
    )
    assert query(
        db_path, "SELECT title, author, language, format, progress_unit FROM books"
    ) == [
        {
            "title": "Tôi thấy hoa vàng trên cỏ xanh",
            "author": "Nguyễn Nhật Ánh",
            "language": "Vietnamese",
            "format": "ebook",
            "progress_unit": "percent",
        }
    ]
    # The next book defaults to the language of the most recently added one.
    assert app.selectbox(key="language_1").value == "Vietnamese"


def test_unit_choice_overrides_the_format_default(app, db_path):
    add_book(app, "Piranesi", pages=270, format="ebook", unit="page")
    assert query(db_path, "SELECT progress_unit FROM books") == [
        {"progress_unit": "page"}
    ]


# --- start and stop ---------------------------------------------------------------


def test_start_button_starts_a_session(app, db_path):
    add_book(app, "Dune")
    app.number_input(key="start_1_0").set_value(10)
    app.button(key="start").click().run()
    assert not app.exception
    assert app.subheader[0].value == "Dune"
    (session,) = query(db_path, "SELECT * FROM sessions")
    assert session["start_pos"] == 10
    assert session["ended_at"] is None


def test_start_with_out_of_range_position_shows_error(app, db_path):
    add_book(app, "Dune")
    app.number_input(key="start_1_0").set_value(500)
    app.button(key="start").click().run()
    assert "between 0 and 412 pages" in app.error[0].value
    assert query(db_path, "SELECT * FROM sessions") == []


def test_stop_logs_the_session_and_prefills_next_start(app, db_path):
    add_book(app, "Dune")
    session_id = start_in_the_past(db_path, book_id=1, start_pos=10, minutes=20)
    app.run()

    stop(app, session_id, 42, note="  great chapter ")
    assert successes(app)[0].startswith("Logged 20 minutes")
    (session,) = query(db_path, "SELECT * FROM sessions")
    assert session["end_pos"] == 42
    assert session["note"] == "great chapter"
    assert app.number_input(key="start_1_42").value == 42


def test_two_full_cycles_through_the_buttons_keep_prefill_current(app, db_path, clock):
    add_book(app, "Dune")
    for session_id, end in [(1, 30), (2, 55)]:
        app.button(key="start").click().run()
        clock(minutes=10)
        app.run()
        stop(app, session_id, end)
        assert successes(app)[0] == "Logged 10 minutes, 0 seconds of reading."
        assert app.number_input(key=f"start_1_{end}").value == end
    assert [
        (s["start_pos"], s["end_pos"]) for s in query(db_path, "SELECT * FROM sessions")
    ] == [(0, 30), (30, 55)]


def test_stop_past_the_last_page_shows_error_and_keeps_session(app, db_path):
    add_book(app, "Dune")
    session_id = start_in_the_past(db_path, book_id=1, start_pos=50, minutes=10)
    app.run()
    stop(app, session_id, 413)
    assert "between 0 and 412 pages" in app.error[0].value
    (session,) = query(db_path, "SELECT * FROM sessions")
    assert session["ended_at"] is None


@pytest.mark.parametrize("action", ["stop", "discard"])
def test_stale_tab_cannot_stop_or_discard_a_newer_session(db_path, clock, action):
    tab_a = open_tracker()
    add_book(tab_a, "Dune")
    tab_a.button(key="start").click().run()  # session 1
    clock(minutes=30)
    tab_a.run()
    tab_b = open_tracker()  # a second tab, still showing session 1

    stop(tab_a, 1, 35)
    clock(minutes=5)
    tab_a.button(key="start").click().run()  # session 2, starting at page 35
    clock(minutes=5)

    if action == "stop":
        tab_b.number_input(key="end_pos_1").set_value(40)
    tab_b.button(key=f"{action}_1").click().run()
    assert not tab_b.exception
    assert query(db_path, "SELECT session_id, start_pos, end_pos FROM sessions") == [
        {"session_id": 1, "start_pos": 0, "end_pos": 35},
        {"session_id": 2, "start_pos": 35, "end_pos": None},
    ]


def test_reaching_the_last_page_offers_to_mark_finished(app, db_path):
    add_book(app, "Dune")
    add_book(app, "Emma", pages=474)
    session_id = start_in_the_past(db_path, book_id=1, start_pos=400, minutes=10)
    app.run()

    stop(app, session_id, 412)
    app.button(key="mark_finished").click().run()
    assert not app.exception
    assert query(db_path, "SELECT title, status FROM books") == [
        {"title": "Dune", "status": "finished"},
        {"title": "Emma", "status": "reading"},
    ]
    # The picker moves on to the next book being read.
    assert app.selectbox(key="start_book").value == 2


def test_percent_book_at_100_offers_to_mark_finished(app, db_path):
    add_book(app, "Piranesi", pages=None, format="ebook")
    session_id = start_in_the_past(db_path, book_id=1, start_pos=95, minutes=10)
    app.run()
    stop(app, session_id, 100)
    assert "mark_finished" in {button.key for button in app.button}


def test_book_added_mid_session_does_not_hijack_the_picker(app, db_path):
    add_book(app, "Dune")
    session_id = start_in_the_past(db_path, book_id=1, start_pos=10, minutes=10)
    app.run()
    add_book(app, "Emma", pages=474)
    stop(app, session_id, 20)
    assert app.selectbox(key="start_book").value == 1


def test_switching_books_prefills_each_books_own_position(app, db_path):
    add_book(app, "Dune")
    add_book(app, "Emma", pages=474)
    session_id = start_in_the_past(db_path, book_id=1, start_pos=10, minutes=10)
    app.run()
    stop(app, session_id, 42)

    app.selectbox(key="start_book").set_value(2).run()
    assert app.number_input(key="start_2_0").value == 0
    app.selectbox(key="start_book").set_value(1).run()
    assert app.number_input(key="start_1_42").value == 42


def test_discarding_a_session_deletes_it(app, db_path):
    add_book(app, "Dune")
    app.button(key="start").click().run()
    (session,) = query(db_path, "SELECT * FROM sessions")
    app.button(key=f"discard_{session['session_id']}").click().run()
    assert not app.exception
    assert query(db_path, "SELECT * FROM sessions") == []
    assert successes(app) == ["Session discarded."]


# --- expanders --------------------------------------------------------------------


def test_log_a_past_session_and_start_prefill_follows(app, db_path):
    add_book(app, "Dune")
    started = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=3)
    app.datetime_input(key="past_started_0").set_value(started)
    app.number_input(key="past_minutes_0").set_value(45)
    app.number_input(key="past_to_0_1_0").set_value(30)
    app.button(key="log_past").click().run()
    assert not app.exception
    assert successes(app) == ["Logged 45 minutes, 0 seconds of *Dune*."]

    (session,) = query(db_path, "SELECT * FROM sessions")
    start = log.parse_timestamp(session["started_at"])
    end = log.parse_timestamp(session["ended_at"])
    assert end - start == timedelta(minutes=45)
    assert start.utcoffset() == datetime.now().astimezone().utcoffset()
    assert (session["start_pos"], session["end_pos"]) == (0, 30)
    assert app.number_input(key="start_1_30").value == 30
    assert app.number_input(key="past_from_1_1_30").value == 30


def test_log_a_past_session_overlap_is_reported(app, db_path):
    add_book(app, "Dune")
    start_in_the_past(db_path, book_id=1, start_pos=0, minutes=30)  # still active
    app.run()
    started = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=50)
    app.datetime_input(key="past_started_0").set_value(started)
    app.button(key="log_past").click().run()
    assert "overlaps" in app.error[0].value


def test_status_expander_updates_the_book(app, db_path):
    add_book(app, "Dune")
    app.button_group(key="status_1_reading").set_value("abandoned")
    app.button(key="update_status").click().run()
    assert not app.exception
    assert query(db_path, "SELECT status FROM books") == [{"status": "abandoned"}]
    assert successes(app) == ["*Dune* is now abandoned."]
    # The control now reflects the stored status instead of the old default.
    assert app.button_group(key="status_1_abandoned").value == "abandoned"

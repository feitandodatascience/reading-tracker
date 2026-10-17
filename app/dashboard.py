"""Public reading dashboard: current book, habit, weekly goal, pace, timeline.

Run it from the repo root:

    uv run streamlit run app/dashboard.py

It reads only public data, never data/raw/: the exported data/processed/*.parquet
or the synthetic data/demo/demo.db. Demo data always carries a "Demo data" badge.
"""

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from reading_tracker import brand, db, eta, export, features

TEMPLATE = brand.register_template()
PROCESSED_DIR = Path(
    os.environ.get("READING_TRACKER_PROCESSED_DIR") or db.PROCESSED_DIR
)
WEEKS_SHOWN = 26
CHART_CONFIG = {"displayModeBar": False, "responsive": True}
FORMAT_LABELS = {"physical": "Physical", "ebook": "Ebook", "audio": "Audiobook"}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# --- data ------------------------------------------------------------------------


def has_real_data() -> bool:
    return all(
        (PROCESSED_DIR / f"{t}.parquet").is_file() for t in ("books", "sessions")
    )


@st.cache_data(ttl=600, max_entries=4)
def load(source: str, folder: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Public books and sessions: ``"demo"`` (synthetic) or ``"real"`` (exported)."""
    if source == "demo":
        if not db.DEMO_DB_PATH.is_file():
            raise FileNotFoundError("Run `uv run python -m reading_tracker.synthetic`.")
        conn = db.connect(db.DEMO_DB_PATH)
        try:
            return export.to_public(db.read_books(conn), db.read_sessions(conn))
        finally:
            conn.close()
    folder = Path(folder)
    return (
        pd.read_parquet(folder / "books.parquet"),
        pd.read_parquet(folder / "sessions.parquet"),
    )


# --- small helpers ---------------------------------------------------------------


def eyebrow(text: str) -> None:
    """Brand section kicker: uppercase, bold, Olive."""
    st.markdown(f":green[**{text.upper()}**]")


def days(n: int) -> str:
    return f"{n} day" if n == 1 else f"{n} days"


def short(title: str, limit: int = 30) -> str:
    return title if len(title) <= limit else title[: limit - 1] + "…"


def date_range(early: pd.Timestamp | None, late: pd.Timestamp | None) -> str:
    dates = [d for d in (early, late) if d is not None]
    if not dates:
        return "Not yet"
    first, last = min(dates), max(dates)
    if first == last:
        return f"{first:%b %d}"
    return f"{first:%b %d} – {last:%b %d}"


def position_text(book: pd.Series) -> str:
    percent = f"{book['fraction_complete']:.0%}"
    if book["progress_unit"] == "page" and pd.notna(book["total_pages"]):
        page = 0 if pd.isna(book["position"]) else int(book["position"])
        return f"{percent} · page {page} of {int(book['total_pages'])}"
    return f"{percent} complete"


# --- charts ----------------------------------------------------------------------


def heatmap_figure(
    daily: pd.DataFrame, start: pd.Timestamp, today: pd.Timestamp
) -> go.Figure:
    """Calendar heatmap: one column per week, one row per weekday."""
    days = pd.DataFrame({"date": pd.date_range(start, today, freq="D")})
    days = days.merge(daily, on="date", how="left").fillna({"minutes": 0.0})
    days["week"] = days["date"] - pd.to_timedelta(days["date"].dt.weekday, unit="D")
    days["weekday"] = days["date"].dt.weekday
    days["label"] = (
        days["date"].dt.strftime("%a %d %b %Y")
        + " · "
        + days["minutes"].round().astype(int).astype(str)
        + " min"
    )
    z = days.pivot(index="weekday", columns="week", values="minutes")
    text = days.pivot(index="weekday", columns="week", values="label")
    fig = go.Figure(
        go.Heatmap(
            z=z.values,
            x=z.columns,
            y=[WEEKDAYS[i] for i in z.index],
            text=text.values,
            hovertemplate="%{text}<extra></extra>",
            colorscale=brand.HEATMAP_COLORSCALE,
            zmin=0,
            xgap=2,
            ygap=2,
            showscale=False,
        )
    )
    fig.update_layout(
        template=TEMPLATE,
        height=250,
        yaxis={"autorange": "reversed", "showgrid": False, "ticks": ""},
        xaxis={"showgrid": False, "tickformat": "%b", "dtick": "M1", "ticks": ""},
    )
    return fig


def weekly_figure(daily: pd.DataFrame, today: pd.Timestamp, goal: int) -> go.Figure:
    """Minutes per week as bars, the current week in Clay, the goal as a line."""
    weeks = daily.assign(
        week=daily["date"] - pd.to_timedelta(daily["date"].dt.weekday, unit="D")
    )
    weekly = weeks.groupby("week", as_index=False)["minutes"].sum().tail(WEEKS_SHOWN)
    this_week = today - pd.Timedelta(days=today.weekday())
    colors = [brand.CLAY if w == this_week else brand.OLIVE for w in weekly["week"]]
    fig = go.Figure(
        go.Bar(
            x=weekly["week"],
            y=weekly["minutes"],
            marker={"color": colors, "cornerradius": 4},
            hovertemplate="Week of %{x|%d %b}<br>%{y:.0f} min<extra></extra>",
        )
    )
    if goal > 0:
        fig.add_hline(
            y=goal,
            line={"color": brand.ESPRESSO, "dash": "dash", "width": 2},
            annotation={
                "text": f"Goal {goal} min",
                "font": {"color": brand.ESPRESSO},
                "xanchor": "right",
                "bgcolor": brand.SAND,
            },
            annotation_position="top right",
        )
    fig.update_layout(
        template=TEMPLATE,
        height=280,
        bargap=0.25,
        yaxis={"title": "minutes"},
        xaxis={"tickformat": "%b %d", "showgrid": False},
    )
    return fig


def pace_figure(paced: pd.DataFrame, group: str) -> go.Figure:
    """One row per category: every session as a dot, with a box for the spread."""
    order = (
        paced.groupby(group)["pace"]
        .median()
        .sort_values(ascending=False)
        .index.tolist()
    )
    fig = go.Figure()
    for category in order:
        values = paced.loc[paced[group] == category, "pace"]
        fig.add_trace(
            go.Box(
                x=values,
                name=str(category),
                orientation="h",
                boxpoints="all",
                jitter=0.5,
                pointpos=0,
                marker={"color": brand.OLIVE, "size": 8, "opacity": 0.55},
                line={"color": brand.ESPRESSO, "width": 2},
                fillcolor="rgba(0,0,0,0)",
                hovertemplate="%{x:.2f} pages/min<extra>" + str(category) + "</extra>",
            )
        )
    fig.update_layout(
        template=TEMPLATE,
        height=90 + 48 * len(order),
        showlegend=False,
        xaxis={"title": "pages per minute", "rangemode": "tozero"},
        yaxis={"autorange": "reversed", "showgrid": False},
    )
    return fig


def timeline_figure(done: pd.DataFrame) -> go.Figure:
    """One bar per finished or abandoned book, from first to last session."""
    data = done.sort_values("first_read").assign(
        book=lambda d: d["title"].map(short),
        until=lambda d: d["last_read"] + pd.Timedelta(days=1),
        outcome=lambda d: d["status"].str.capitalize(),
    )
    fig = px.timeline(
        data,
        x_start="first_read",
        x_end="until",
        y="book",
        color="outcome",
        color_discrete_map={
            label.capitalize(): color for label, color in brand.STATUS_COLORS.items()
        },
        hover_name="title",
        hover_data={"book": False, "until": False, "outcome": True, "author": True},
        category_orders={"book": data["book"].tolist()},
    )
    fig.update_traces(marker={"cornerradius": 4})
    fig.update_layout(
        template=TEMPLATE,
        height=90 + 28 * len(data),
        legend_title_text="",
        xaxis={"title": "", "tickformat": "%b"},
        yaxis={"title": "", "showgrid": False},
    )
    return fig


# --- page ------------------------------------------------------------------------

st.set_page_config(page_title="Reading journey", layout="wide")

real_available = has_real_data()
with st.sidebar:
    st.header("Feitan")
    demo = st.toggle(
        "Demo data",
        value=not real_available,
        disabled=not real_available,
        help="Synthetic history from synthetic.py, so the dashboard works anywhere.",
    )
    if not real_available:
        st.caption("No exported data yet, so the dashboard shows demo data.")
    goal = st.number_input(
        "Weekly goal (minutes)", min_value=0, max_value=5000, value=210, step=30
    )

eyebrow("A personal reading tracker")
st.title("Reading journey")
if demo:
    st.badge("Demo data", icon=":material/science:", color="orange")
    st.caption("Synthetic history, not real reading.")

books, sessions = load("demo" if demo else "real", str(PROCESSED_DIR))
prepared = features.prepare_sessions(sessions, books)
if prepared.empty:
    st.info("No finished reading sessions yet.")
    st.stop()
progress = features.book_progress(books, sessions)
# Demo data ends on a fixed day; real data is "as of today".
today = prepared["date"].max() if demo else pd.Timestamp.now().normalize()
daily = features.daily_minutes(prepared, end=today)

# 1. Current book -------------------------------------------------------------------
reading = progress[progress["status"] == "reading"].sort_values(
    "last_read", ascending=False, na_position="last"
)
if not reading.empty:
    for column, (_, book) in zip(
        st.columns(min(len(reading), 2)), reading.head(2).iterrows(), strict=False
    ):
        with column, st.container(border=True):
            eyebrow(
                "Listening to" if book["format"] == "audio" else "Currently reading"
            )
            st.subheader(book["title"])
            details = [book["author"], book["language"], FORMAT_LABELS[book["format"]]]
            st.caption(" · ".join(str(d) for d in details if pd.notna(d)))
            st.progress(float(book["fraction_complete"]), text=position_text(book))
            estimate = eta.baseline_eta(book, prepared, today)
            if estimate:
                st.metric(
                    "Estimated finish",
                    date_range(estimate["eta_early"], estimate["eta_late"]),
                    help="Baseline: what's left ÷ recent pace ÷ recent minutes per day."
                    " The range uses faster and slower recent sessions.",
                )
                st.caption(
                    f"About {estimate['remaining']:.0f} {estimate['unit']} left at"
                    f" {estimate['minutes_per_day']:.0f} min a day."
                )
            else:
                st.caption("Not enough recent reading to estimate a finish date.")

# 2. Habit ----------------------------------------------------------------------------
st.divider()
eyebrow("Habit")
st.subheader("Daily reading")
start = today - pd.Timedelta(weeks=WEEKS_SHOWN)
start -= pd.Timedelta(days=start.weekday())
recent = daily[daily["date"] >= start]
streak = features.streaks(daily, today)
current_col, longest_col, days_col, average_col = st.columns(4)
current_col.metric("Current streak", days(streak["current"]))
longest_col.metric("Longest streak", days(streak["longest"]))
days_col.metric("Reading days", f"{int((recent['minutes'] > 0).sum())}")
average_col.metric("Average per day", f"{recent['minutes'].mean():.0f} min")
st.plotly_chart(heatmap_figure(daily, start, today), theme=None, config=CHART_CONFIG)
st.caption(
    "Darker squares mean more minutes; the palest ones are days without reading."
)

# 3. Weekly goal ----------------------------------------------------------------------
st.subheader("Weekly minutes")
st.plotly_chart(weekly_figure(daily, today, goal), theme=None, config=CHART_CONFIG)
this_week = daily[daily["date"] >= today - pd.Timedelta(days=today.weekday())]
st.caption(
    f"This week so far: {this_week['minutes'].sum():.0f} of {goal} minutes"
    " (current week in Clay)."
)

# 4. Pace -----------------------------------------------------------------------------
st.divider()
eyebrow("Pace")
st.subheader("How fast I read")
group = st.segmented_control(
    "Compare by",
    ["genre", "format", "language"],
    default="genre",
    required=True,
    format_func=str.capitalize,
)
paced = prepared.dropna(subset=["pace"]).copy()
paced["format"] = paced["format"].map(FORMAT_LABELS)
paced[group] = paced[group].fillna("Unknown")
if paced.empty:
    st.info("No page-based sessions yet.")
else:
    st.plotly_chart(pace_figure(paced, group), theme=None, config=CHART_CONFIG)
    st.caption("Each dot is a session. Audiobooks are tracked but not part of pace.")

# 5. Timeline -------------------------------------------------------------------------
st.divider()
eyebrow("Books")
st.subheader("Finished and abandoned")
done = progress[
    progress["status"].isin(["finished", "abandoned"]) & progress["first_read"].notna()
]
if done.empty:
    st.info("No finished or abandoned books yet.")
else:
    st.plotly_chart(timeline_figure(done), theme=None, config=CHART_CONFIG)

with st.expander("Show the numbers"):
    table = progress[
        [
            "title",
            "author",
            "language",
            "genre",
            "format",
            "status",
            "fraction_complete",
            "minutes",
            "sessions",
            "first_read",
            "last_read",
        ]
    ].sort_values("first_read", ascending=False)
    st.dataframe(
        table,
        hide_index=True,
        column_config={
            "fraction_complete": st.column_config.ProgressColumn(
                "Progress", min_value=0.0, max_value=1.0, format="percent"
            ),
            "minutes": st.column_config.NumberColumn("Minutes", format="%.0f"),
            "first_read": st.column_config.DateColumn("First read"),
            "last_read": st.column_config.DateColumn("Last read"),
        },
    )

st.caption(
    "Public data only: notes are never exported and times are rounded down to the"
    " hour. [Source on GitHub](https://github.com/feitandodatascience/reading-tracker)"
)

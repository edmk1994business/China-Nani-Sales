"""Date presets, aggregation levels, calendar padding and comparison windows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from . import config

PRESETS = ["Today", "Yesterday", "This Week", "Last Week", "This Month",
           "Last Month", "This Year", "Last Year", "Custom Range"]
LEVELS = ["Daily", "Weekly", "Monthly"]
COMPARE_BASES = ["Prior period", "Same period last year"]

UNIT = {"Daily": "day", "Weekly": "week", "Monthly": "month"}


@dataclass(frozen=True)
class Window:
    start: date
    end: date
    label: str

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True)
class Bucket:
    """One row/bar of the aggregated view (a day, a calendar week or a calendar month)."""
    start: date
    end: date
    label: str


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def today_local() -> date:
    return datetime.now(ZoneInfo(config.TIMEZONE)).date()


def fmt_range(a: date, b: date) -> str:
    if a == b:
        return a.strftime("%a %d %b %Y")
    if a.year == b.year:
        return f"{a.strftime('%d %b')} – {b.strftime('%d %b %Y')}"
    return f"{a.strftime('%d %b %Y')} – {b.strftime('%d %b %Y')}"


def month_end(d: date) -> date:
    return (d.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _months_spanned(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month) + 1


# --------------------------------------------------------------------------- #
# Current window
# --------------------------------------------------------------------------- #
def resolve(preset: str, today: date, custom: tuple[date, date] | None = None) -> Window:
    """Current window for a preset. 'This …' presets run to today (period-to-date)."""
    t = today
    if preset == "Today":
        s = e = t
    elif preset == "Yesterday":
        s = e = t - timedelta(days=1)
    elif preset == "This Week":
        s, e = week_start(t), t
    elif preset == "Last Week":
        s = week_start(t) - timedelta(days=7)
        e = s + timedelta(days=6)
    elif preset == "This Month":
        s, e = t.replace(day=1), t
    elif preset == "Last Month":
        e = t.replace(day=1) - timedelta(days=1)
        s = e.replace(day=1)
    elif preset == "This Year":
        s, e = date(t.year, 1, 1), t
    elif preset == "Last Year":
        s, e = date(t.year - 1, 1, 1), date(t.year - 1, 12, 31)
    else:  # Custom Range
        s, e = custom if custom else (t, t)
        if s > e:
            s, e = e, s
    return Window(s, e, fmt_range(s, e))


def pad(w: Window, level: str) -> Window:
    """Extend a window to whole calendar weeks (Mon–Sun) or whole calendar months."""
    if level == "Weekly":
        s, e = week_start(w.start), week_start(w.end) + timedelta(days=6)
    elif level == "Monthly":
        s, e = w.start.replace(day=1), month_end(w.end)
    else:
        return w
    return Window(s, e, fmt_range(s, e))


def effective_end(w: Window, data_end: date | None) -> date:
    """Last day that can hold data: the window end, or the latest loaded day if earlier."""
    if data_end is None or data_end >= w.end or data_end < w.start:
        return w.end
    return data_end


# --------------------------------------------------------------------------- #
# Comparison window
# --------------------------------------------------------------------------- #
def _comparison_daily(preset: str, cur: Window, basis: str) -> Window:
    """Day-level comparison (unchanged behaviour)."""
    s, e = cur.start, cur.end
    if basis == "Same period last year":
        if cur.days <= 7:
            ps, pe = s - timedelta(days=364), e - timedelta(days=364)
        else:
            ps, pe = s - relativedelta(years=1), e - relativedelta(years=1)
        return Window(ps, pe, fmt_range(ps, pe))

    if preset in ("Today", "Yesterday"):
        ps = pe = s - timedelta(days=1)
    elif preset in ("This Week", "Last Week"):
        ps, pe = s - timedelta(days=7), e - timedelta(days=7)
    elif preset in ("This Month", "Last Month"):
        ps = s - relativedelta(months=1)
        pe = s - timedelta(days=1) if preset == "Last Month" else min(ps + timedelta(days=cur.days - 1),
                                                                       s - timedelta(days=1))
    elif preset in ("This Year", "Last Year"):
        ps, pe = s - relativedelta(years=1), e - relativedelta(years=1)
    else:
        pe = s - timedelta(days=1)
        ps = pe - timedelta(days=cur.days - 1)
    return Window(ps, pe, fmt_range(ps, pe))


def comparison(preset: str, cur: Window, basis: str, level: str, data_end: date | None) -> Window:
    """Comparison window.

    Daily   : day vs prior day / week vs prior week / month-to-date like-for-like (see _comparison_daily).
    Weekly  : the same number of whole weeks immediately before (or 52 weeks earlier for last year).
    Monthly : the same number of whole months immediately before (or 12 months earlier).
    If the current padded window is still in progress (no data yet for its last days), the
    comparison window is cut at the equivalent day, so the last week/month is like-for-like.
    """
    if level == "Daily":
        return _comparison_daily(preset, cur, basis)

    eff = effective_end(cur, data_end)
    ly = basis == "Same period last year"
    if level == "Weekly":
        shift = timedelta(days=364 if ly else 7 * max(cur.days // 7, 1))
        ps, pe_full, pe_eff = cur.start - shift, cur.end - shift, eff - shift
    else:
        rd = relativedelta(years=1) if ly else relativedelta(months=_months_spanned(cur.start, cur.end))
        ps = cur.start - rd
        pe_full = month_end(cur.end - rd)
        pe_eff = min(eff - rd, pe_full)
    pe = pe_eff if eff < cur.end else pe_full
    return Window(ps, pe, fmt_range(ps, pe))


# --------------------------------------------------------------------------- #
# Buckets
# --------------------------------------------------------------------------- #
def buckets(start: date, end: date, level: str) -> list[Bucket]:
    """Split [start, end] into day / calendar-week / calendar-month buckets (edges clipped)."""
    out: list[Bucket] = []
    d = start
    while d <= end:
        if level == "Weekly":
            b_start, b_end = week_start(d), week_start(d) + timedelta(days=6)
        elif level == "Monthly":
            b_start, b_end = d.replace(day=1), month_end(d)
        else:
            b_start = b_end = d
        s, e = max(b_start, start), min(b_end, end)
        out.append(Bucket(s, e, bucket_label(s, e, level, full=(s == b_start and e == b_end))))
        d = e + timedelta(days=1)
    return out


def bucket_label(s: date, e: date, level: str, full: bool = True) -> str:
    if level == "Weekly":
        wk = s.isocalendar()[1]
        return f"W{wk:02d} · {s:%d %b}–{e:%d %b} {e:%y}"
    if level == "Monthly":
        return f"{s:%b %Y}" if full else f"{s:%b %Y} (to {e:%d %b})"
    return s.strftime("%a %d %b %Y")

"""Date presets and comparison-window logic."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from . import config

PRESETS = ["Today", "Yesterday", "This Week", "Last Week", "This Month",
           "Last Month", "This Year", "Last Year", "Custom Range"]

COMPARE_BASES = ["Prior period", "Same period last year"]


@dataclass(frozen=True)
class Window:
    start: date
    end: date
    label: str

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


def today_local() -> date:
    return datetime.now(ZoneInfo(config.TIMEZONE)).date()


def _fmt(a: date, b: date) -> str:
    if a == b:
        return a.strftime("%a %d %b %Y")
    if a.year == b.year:
        return f"{a.strftime('%d %b')} – {b.strftime('%d %b %Y')}"
    return f"{a.strftime('%d %b %Y')} – {b.strftime('%d %b %Y')}"


def resolve(preset: str, today: date, custom: tuple[date, date] | None = None) -> Window:
    """Current window for a preset. 'This …' presets run to today (period-to-date)."""
    t = today
    if preset == "Today":
        s = e = t
    elif preset == "Yesterday":
        s = e = t - timedelta(days=1)
    elif preset == "This Week":
        s, e = t - timedelta(days=t.weekday()), t
    elif preset == "Last Week":
        s = t - timedelta(days=t.weekday() + 7)
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
    return Window(s, e, _fmt(s, e))


def comparison(preset: str, cur: Window, basis: str) -> Window:
    """Comparison window.

    Prior period:
      Today/Yesterday -> the day before; weeks -> previous week; months -> previous
      month; years -> previous year. Period-to-date presets are compared like-for-like
      (e.g. 1–15 Oct vs 1–15 Sep). Custom ranges use the same number of days right before.
    Same period last year:
      ranges up to 7 days shift 364 days (same weekday); longer ranges shift one calendar year.
    """
    s, e = cur.start, cur.end
    if basis == "Same period last year":
        if cur.days <= 7:
            ps, pe = s - timedelta(days=364), e - timedelta(days=364)
        else:
            ps, pe = s - relativedelta(years=1), e - relativedelta(years=1)
        return Window(ps, pe, _fmt(ps, pe))

    if preset in ("Today", "Yesterday"):
        ps = pe = s - timedelta(days=1)
    elif preset in ("This Week", "Last Week"):
        ps, pe = s - timedelta(days=7), e - timedelta(days=7)
    elif preset in ("This Month", "Last Month"):
        ps = s - relativedelta(months=1)
        if preset == "Last Month":
            pe = s - timedelta(days=1)                      # full previous month
        else:
            pe = min(ps + timedelta(days=cur.days - 1),      # month-to-date like-for-like
                     s - timedelta(days=1))
    elif preset in ("This Year", "Last Year"):
        ps = s - relativedelta(years=1)
        pe = e - relativedelta(years=1)
    else:
        pe = s - timedelta(days=1)
        ps = pe - timedelta(days=cur.days - 1)
    return Window(ps, pe, _fmt(ps, pe))


def granularity(days: int) -> str:
    if days <= 45:
        return "D"
    if days <= 190:
        return "W"
    return "M"

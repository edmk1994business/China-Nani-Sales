"""KPI maths. Ratios are always recomputed from sums (never averaged)."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .periods import Window

SUMS = ["sales_gross", "sales_net", "checks", "cogs"]


@dataclass
class KPI:
    key: str
    label: str
    kind: str              # money | count | pct
    higher_is_better: bool = True


KPIS = [
    KPI("sales_gross", "Sales before discount", "money"),
    KPI("sales_net", "Sales after discount", "money"),
    KPI("checks", "Checks", "count"),
    KPI("aov", "Average check (AOV)", "money"),
    KPI("cogs", "COGS", "money", higher_is_better=False),
    KPI("cogs_pct", "COGS %", "pct", higher_is_better=False),
]


def window_slice(df: pd.DataFrame, w: Window) -> pd.DataFrame:
    if df.empty:
        return df
    m = (df["date"] >= pd.Timestamp(w.start)) & (df["date"] <= pd.Timestamp(w.end))
    return df[m]


def add_ratios(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    t["aov"] = (t["sales_net"] / t["checks"]).where(t["checks"] > 0)
    t["cogs_pct"] = (t["cogs"] / t["sales_net"]).where(t["sales_net"] > 0)
    return t


def totals(df: pd.DataFrame) -> dict:
    s = {c: float(df[c].sum()) if not df.empty else 0.0 for c in SUMS}
    s["aov"] = s["sales_net"] / s["checks"] if s["checks"] else None
    s["cogs_pct"] = s["cogs"] / s["sales_net"] if s["sales_net"] else None
    s["has_data"] = not df.empty
    return s


def delta(cur, prev, kind: str):
    """Returns (absolute delta, relative delta). For pct KPIs the absolute delta is in pp."""
    if cur is None or prev is None:
        return None, None
    d = cur - prev
    if kind == "pct":
        return d, None
    rel = d / prev if prev else None
    return d, rel


def breakdown(df: pd.DataFrame, by: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[by, *SUMS, "aov", "cogs_pct"])
    t = df.groupby(by, as_index=False)[SUMS].sum()
    return add_ratios(t).sort_values("sales_net", ascending=False)


def timeseries(df: pd.DataFrame, by: str | None, freq: str, shift_days: int = 0) -> pd.DataFrame:
    """Sales by period bucket. shift_days moves comparison data onto the current axis."""
    if df.empty:
        return pd.DataFrame(columns=["bucket", "sales_net"] + ([by] if by else []))
    d = df.copy()
    d["date"] = d["date"] + pd.Timedelta(days=shift_days)
    d["bucket"] = d["date"].dt.to_period(freq).dt.start_time
    keys = ["bucket"] + ([by] if by else [])
    return d.groupby(keys, as_index=False)[SUMS].sum()

"""ChinaTown & Nani — Executive Sales Dashboard (Streamlit).

Data: iiko OLAP exports on Dropbox
  * Sales History.xlsx  – previous year (static)
  * Update Sales.xlsx   – current year (overwritten daily ~11:30 by the RPA bot)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from dashboard import config, data, metrics, periods, ui

st.set_page_config(
    page_title="Sales Dashboard · ChinaTown & Nani",
    page_icon=str(config.ASSETS / "chinatown.png"),
    layout="wide",
    initial_sidebar_state="auto",   # collapses automatically on phones
)

SUMS = ["sales_gross", "sales_net", "checks", "cogs"]
RECORD_DIMS = ["brand", "channel", "payment_label"]

# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
if st.query_params.get("refresh"):          # RPA bot opens ?refresh=1 after each export
    data.clear_cache()
    st.query_params.clear()


@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def get_data():
    res = data.load_sales()
    fetched = datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%d %b %H:%M")
    return res.df, res.messages, fetched


with st.spinner("Loading sales data from Dropbox…"):
    df_all, load_msgs, fetched_at = get_data()

# --------------------------------------------------------------------------- #
# Navigation state (cards on the overview jump to a section)
# --------------------------------------------------------------------------- #
if "section" not in st.session_state:
    st.session_state["section"] = "General"


def go_to(section: str) -> None:
    st.session_state["section"] = section


# --------------------------------------------------------------------------- #
# Sidebar filters
# --------------------------------------------------------------------------- #
today = periods.today_local()
with st.sidebar:
    st.markdown('<div class="sb-title">Brand</div>', unsafe_allow_html=True)
    brand = st.radio("Brand", config.BRANDS, index=0, label_visibility="collapsed")

    st.markdown('<div class="sb-title">Period</div>', unsafe_allow_html=True)
    preset = st.selectbox("Period", periods.PRESETS, index=1, label_visibility="collapsed")
    custom = None
    if preset == "Custom Range":
        min_d = df_all["date"].min().date() if not df_all.empty else today.replace(month=1, day=1)
        default_start = today.replace(day=1) if today.day > 1 else min_d
        rng = st.date_input("Custom range", value=(default_start, today), min_value=min_d,
                            max_value=today, format="DD.MM.YYYY")
        if isinstance(rng, (tuple, list)) and len(rng) == 2:
            custom = (rng[0], rng[1])
        elif isinstance(rng, (tuple, list)) and len(rng) == 1:
            custom = (rng[0], rng[0])

    st.markdown('<div class="sb-title">Aggregation level</div>', unsafe_allow_html=True)
    level = st.radio("Aggregation level", periods.LEVELS, index=0, horizontal=True,
                     label_visibility="collapsed",
                     help="Weekly and Monthly extend the selected dates to whole calendar weeks / months.")

    include_today = st.toggle(
        "Include today (partial day)", value=False,
        help="The 11:30 export only holds this morning's sales. Excluding today keeps period-to-date "
             "comparisons fair. 'Today' preset always includes it.")

    st.markdown('<div class="sb-title">Comparison</div>', unsafe_allow_html=True)
    compare_on = st.toggle("Compare with prior period", value=True)
    basis = periods.COMPARE_BASES[0]
    if compare_on:
        basis = st.radio("Compare against", periods.COMPARE_BASES, index=0, label_visibility="collapsed")

    st.divider()
    if st.button("↻  Refresh data", width="stretch"):
        data.clear_cache()
        get_data.clear()
        st.rerun()
    st.caption(f"Live file is updated daily at 11:30 by the iiko bot. Cache: {config.CACHE_TTL_SECONDS // 60} min.")

theme = config.THEMES[brand]
ui.inject_css(theme, brand)

for m in load_msgs:
    st.warning(m)
if df_all.empty:
    st.error("No data could be loaded. Check the Dropbox links in `.streamlit/secrets.toml`.")
    st.stop()

# --------------------------------------------------------------------------- #
# Windows & buckets
# --------------------------------------------------------------------------- #
df_brand = df_all if brand == "All brands" else df_all[df_all["brand"] == brand]
latest = df_brand["date"].max().date() if not df_brand.empty else None
data_through = latest.strftime("%d %b %Y") if latest else "—"

# Today's rows are only a partial day (export runs at 11:30) → leave them out unless asked for.
cutoff = today if (include_today or preset == "Today") else today - timedelta(days=1)
excluded_today = latest is not None and latest > cutoff
df_brand = df_brand[df_brand["date"] <= pd.Timestamp(cutoff)]
data_end = min(latest, cutoff) if latest else None

selected_w = periods.resolve(preset, today, custom)
if selected_w.start <= cutoff < selected_w.end:          # period-to-date presets stop at the cutoff
    selected_w = periods.Window(selected_w.start, cutoff, periods.fmt_range(selected_w.start, cutoff))
cur_w = periods.pad(selected_w, level)
cur_eff_end = periods.effective_end(cur_w, data_end)
prev_w = periods.comparison(preset, cur_w, basis, level, data_end) if compare_on else None

cur_df = metrics.window_slice(df_brand, cur_w)
prev_df = metrics.window_slice(df_brand, prev_w) if prev_w else None
if prev_df is not None and prev_df.empty:
    st.info(f"No data available for the comparison period ({prev_w.label}). Deltas are hidden.")
    prev_w, prev_df = None, None

data_start = df_brand["date"].min().date() if not df_brand.empty else None
if prev_w and data_start and (data_start - prev_w.start).days > 3:   # small gap = closed days (e.g. 1 Jan)
    st.warning(f"The comparison period ({prev_w.label}) starts before the first day in the files "
               f"({data_start:%d %b %Y}), so deltas only cover part of it.")

cur_buckets = periods.buckets(cur_w.start, cur_eff_end, level)
prev_buckets = periods.buckets(prev_w.start, prev_w.end, level) if prev_w else []

unit = periods.UNIT[level]
notes = []
if (cur_w.start, cur_w.end) != (selected_w.start, selected_w.end):
    notes.append(f"Extended to full calendar {unit}s")
if cur_eff_end < cur_w.end:
    notes.append(f"{unit.capitalize()} in progress · data through {cur_eff_end:%d %b}"
                 + (" · compared like-for-like" if prev_w else ""))
if level != "Daily":
    notes.append(f"{level} view")
if excluded_today and cur_w.start <= today <= cur_w.end:
    notes.append("Today's partial data excluded")

period_label = cur_w.label if preset == "Custom Range" else f"{preset} · {cur_w.label}"
ui.hero(brand, theme, period_label, prev_w.label if prev_w else None, data_through, fetched_at, notes)

# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def aligned_prev(p_df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Comparison totals per bucket, bucket i ↔ current bucket i, x set to the current bucket date."""
    if p_df is None:
        return None
    p = data.aggregate(p_df, prev_buckets)
    p = p[p["bucket_idx"] < len(cur_buckets)].copy()
    p["x"] = [pd.Timestamp(cur_buckets[i].start) for i in p["bucket_idx"]]
    return p


def period_table(c_df: pd.DataFrame, p_df: pd.DataFrame | None) -> str:
    """Performance per day / week / month with the aligned comparison period."""
    cur = data.aggregate(c_df, cur_buckets)
    cur_rows = cur.set_index("period")[SUMS]
    prev_rows, compared = None, None
    if p_df is not None:
        p = data.aggregate(p_df, prev_buckets)
        # matched buckets take the current label; unmatched extra ones keep their own (counted in Total only)
        p.index = [cur_buckets[i].label if i < len(cur_buckets) else f"__extra_{i}" for i in p["bucket_idx"]]
        prev_rows = p[SUMS]
        compared = [prev_buckets[i].label if i < len(prev_buckets) else "—" for i in range(len(cur_buckets))]
    return ui.variance_table(cur_rows, prev_rows, level[:-2] if level != "Daily" else "Day",
                             compared_with=compared, scroll=len(cur_rows) > 12)


def breakdown_table(c_df: pd.DataFrame, p_df: pd.DataFrame | None, key: str, label: str) -> str:
    cur = metrics.breakdown(c_df, key).set_index(key)[SUMS]
    prev = metrics.breakdown(p_df, key).set_index(key)[SUMS] if p_df is not None else None
    if prev is not None:   # keep rows that only exist in the comparison period
        cur = cur.reindex(cur.index.append(prev.index.difference(cur.index))).fillna(0.0)
    return ui.variance_table(cur, prev, label)


def records_expander(c_df: pd.DataFrame, p_df: pd.DataFrame | None, key: str) -> None:
    cur = data.aggregate(c_df, cur_buckets, by=RECORD_DIMS, fill_empty=False)
    prev = data.aggregate(p_df, prev_buckets, by=RECORD_DIMS, fill_empty=False) if p_df is not None else None
    with st.expander(f"Detailed records · {level.lower()} · {len(cur):,} rows", expanded=False):
        if cur.empty:
            st.caption("No records for this selection.")
            return
        table = ui.records_table(cur, prev)
        st.dataframe(ui.style_records(table), width="stretch", hide_index=True, height=420,
                     column_config=ui.RECORDS_COLUMN_CONFIG)
        st.download_button("Download CSV", table.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"sales_{ui.slug(brand)}_{key}_{level.lower()}_{cur_w.start}_{cur_w.end}.csv",
                           mime="text/csv", key=f"dl_{key}")


def kpis(c_df: pd.DataFrame, p_df: pd.DataFrame | None) -> None:
    ui.kpi_cards(metrics.totals(c_df), metrics.totals(p_df) if p_df is not None else None,
                 prev_w.label if prev_w else None)


trend_note = f"{level} buckets" + (" · dotted line = comparison period, aligned bucket by bucket" if prev_w else "")

# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #
def render_general() -> None:
    ui.section_header(ui.brand_icon(brand, theme), "Overview", "Totals across all channels combined")
    if cur_df.empty:
        ui.empty_state(f"No sales recorded for {cur_w.label} yet. Data currently runs through {data_through}."
                       + (" Today's partial data is hidden: switch on 'Include today' in the sidebar."
                          if excluded_today else ""))
        return
    kpis(cur_df, prev_df)

    cur_bd = metrics.breakdown(cur_df, "channel")
    prev_bd = metrics.breakdown(prev_df, "channel") if prev_df is not None else None

    ui.block_title("Channels", "Tap a card to open that channel")
    cols = st.columns(len(config.CHANNELS), gap="small")
    for col, ch in zip(cols, config.CHANNELS):
        with col, st.container(key=f"card_{ui.slug(ch)}"):
            st.markdown(ui.channel_card_html(ch, cur_bd, prev_bd, brand, theme), unsafe_allow_html=True)
            st.button(f"Open {ch}", key=f"open_{ui.slug(ch)}", on_click=go_to, args=(ch,))

    c1, c2 = st.columns([2, 3], gap="medium")
    with c1:
        ui.block_title("Revenue share by channel")
        choice = st.radio("Measure", ["Net sales", "Gross sales", "Checks"], horizontal=True,
                          key="donut_measure", label_visibility="collapsed")
        mkey, mlabel = {"Net sales": ("sales_net", "sales after discount"),
                        "Gross sales": ("sales_gross", "sales before discount"),
                        "Checks": ("checks", "checks")}[choice]
        ui.donut(cur_bd, mkey, mlabel, theme)
        if mkey == "sales_net":
            st.caption("Compliments carry no revenue after discount (0%). Switch to Gross sales to see their menu value.")
    with c2:
        ui.block_title("Sales after discount by channel", trend_note)
        cur_ts = data.aggregate(cur_df, cur_buckets, by=["channel"])
        ui.trend(cur_ts, aligned_prev(prev_df), "channel", config.CHANNELS, ui.channel_colors(theme),
                 theme, level, "sales_net", prev_w.label if prev_w else None)

    ui.block_title("Breakdown by channel")
    ui.show_html(breakdown_table(cur_df, prev_df, "channel", "Channel"))

    if brand == "All brands":
        ui.block_title("Breakdown by brand")
        ui.show_html(breakdown_table(cur_df, prev_df, "brand", "Brand"))

    ui.block_title(f"Performance by {unit}",
                   f"Each {unit} vs the matching {unit} of the comparison period" if prev_w else None)
    ui.show_html(period_table(cur_df, prev_df))

    records_expander(cur_df, prev_df, "general")


def render_channel(channel: str) -> None:
    head, back = st.columns([5, 1], vertical_alignment="center")
    with head:
        ui.section_header(ui.channel_icon(channel, brand, theme), channel, ui.SECTION_DESC[channel])
    with back:
        st.button("← Overview", key=f"back_{ui.slug(channel)}", on_click=go_to, args=("General",), width="stretch")

    c_df = cur_df[cur_df["channel"] == channel]
    p_df = prev_df[prev_df["channel"] == channel] if prev_df is not None else None
    if c_df.empty:
        has_any = not df_brand[df_brand["channel"] == channel].empty
        ui.empty_state(f"No {channel} records for {cur_w.label}."
                       + ("" if has_any else f" This brand has no {channel} data in the files."))
        return
    kpis(c_df, p_df)

    measure = "sales_gross" if channel == "Compliments" else "sales_net"
    m_label = "menu value (before discount)" if channel == "Compliments" else "sales after discount"
    cur_bd = metrics.breakdown(c_df, "payment_label")
    prev_bd = metrics.breakdown(p_df, "payment_label") if p_df is not None else None

    c1, c2 = st.columns([3, 2], gap="medium")
    with c1:
        ui.block_title(f"Trend · {m_label}", trend_note)
        labels = cur_bd["payment_label"].tolist()
        cur_ts = data.aggregate(c_df, cur_buckets, by=["payment_label"])
        ui.trend(cur_ts, aligned_prev(p_df), "payment_label", labels, dict(zip(labels, ui.tints(theme, len(labels)))),
                 theme, level, measure, prev_w.label if prev_w else None)
    with c2:
        ui.block_title("By payment type")
        ui.payment_bars(cur_bd, prev_bd, theme, measure)

    ui.block_title("Breakdown by payment type")
    ui.show_html(breakdown_table(c_df, p_df, "payment_label", "Payment type"))

    ui.block_title(f"Performance by {unit}",
                   f"Each {unit} vs the matching {unit} of the comparison period" if prev_w else None)
    ui.show_html(period_table(c_df, p_df))

    records_expander(c_df, p_df, ui.slug(channel))


with st.container(key="nav"):
    section = st.radio("Section", ui.SECTIONS, horizontal=True, key="section", label_visibility="collapsed")

if section == "General":
    render_general()
else:
    render_channel(section)

st.caption(
    "AOV = sales after discount ÷ checks · COGS % = COGS ÷ sales after discount · "
    "Green = revenue/orders up or costs down · Red = revenue/orders down or costs (COGS, COGS %) up · "
    "Checks are iiko order counts per payment type (an order split across two payment types counts in both). "
    f"Comparison basis: {basis.lower() if compare_on else 'off'}."
)
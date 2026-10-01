"""ChinaTown & Nani — Executive Sales Dashboard (Streamlit).

Data: iiko OLAP exports on Dropbox
  * Sales History.xlsx  – previous year (static)
  * Update Sales.xlsx   – current year (overwritten daily ~11:30 by the RPA bot)
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from dashboard import config, data, metrics, periods, ui

st.set_page_config(
    page_title="Sales Dashboard · ChinaTown & Nani",
    page_icon=str(config.ASSETS / "chinatown.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)

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
        custom = tuple(rng) if isinstance(rng, (tuple, list)) and len(rng) == 2 else (rng[0], rng[0]) if rng else None

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

cur_w = periods.resolve(preset, today, custom)
prev_w = periods.comparison(preset, cur_w, basis) if compare_on else None

# --------------------------------------------------------------------------- #
# Theming (tab logos are injected through CSS)
# --------------------------------------------------------------------------- #
TABS = [
    ("General", None, "All channels combined"),
    ("Hall", "Hall", "Dine-in & direct sales — cash, cards, Idram, transfers"),
    ("Yandex", "Yandex", "Yandex Eats delivery"),
    ("Glovo", "Glovo", "Glovo delivery"),
    ("Buy.am", "Buy.am", "Buy.am delivery"),
    ("Compliments", "Compliments", "Orders closed without payment (compliments / promo)"),
]
tab_icons = [ui.brand_icon(brand, theme)] + [ui.channel_icon(ch, brand, theme) for _, ch, _ in TABS[1:]]
ui.inject_css(theme, tab_icons)

for m in load_msgs:
    st.warning(m)
if df_all.empty:
    st.error("No data could be loaded. Check the Dropbox links in `.streamlit/secrets.toml`.")
    st.stop()

df_brand = df_all if brand == "All brands" else df_all[df_all["brand"] == brand]
data_through = df_brand["date"].max().strftime("%d %b %Y") if not df_brand.empty else "—"

cur_df = metrics.window_slice(df_brand, cur_w)
prev_df = metrics.window_slice(df_brand, prev_w) if prev_w else None
if prev_df is not None and prev_df.empty:
    st.info(f"No data available for the comparison period ({prev_w.label}) — deltas are hidden.")
    prev_w, prev_df = None, None

ui.hero(brand, theme, f"{preset} · {cur_w.label}" if preset != "Custom Range" else cur_w.label,
        prev_w.label if prev_w else None, data_through, fetched_at)

freq = periods.granularity(cur_w.days)
shift = (cur_w.start - prev_w.start).days if prev_w else 0


def tints(n: int) -> list[str]:
    """n distinct shades of the brand accent for payment-type series."""
    base = theme["accent_strong"].lstrip("#"), theme["accent"].lstrip("#")
    out = []
    for i in range(n):
        src = base[0] if i == 0 else base[1]
        mix = 0 if i < 2 else min(0.18 * (i - 1), 0.75)
        r, g, b = (int(src[j:j + 2], 16) for j in (0, 2, 4))
        r, g, b = (int(c + (255 - c) * mix) for c in (r, g, b))
        out.append(f"#{r:02x}{g:02x}{b:02x}")
    return out


def raw_expander(df: pd.DataFrame, key: str) -> None:
    with st.expander(f"Raw records · {len(df):,} rows", expanded=False):
        if df.empty:
            st.caption("No records for this selection.")
            return
        t = ui.raw_table(df)
        st.dataframe(t, width="stretch", hide_index=True, column_config=ui.RAW_COLUMN_CONFIG, height=420)
        st.download_button("Download CSV", t.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"sales_{brand}_{key}_{cur_w.start}_{cur_w.end}.csv".replace(" ", "_"),
                           mime="text/csv", key=f"dl_{key}")


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #
def render_general() -> None:
    ui.section_header(ui.brand_icon(brand, theme), "Overview", "All channels combined")
    cur_t = metrics.totals(cur_df)
    prev_t = metrics.totals(prev_df) if prev_df is not None else None
    if not cur_t["has_data"]:
        ui.empty_state(f"No sales recorded for {cur_w.label} yet. Data currently runs through {data_through}.")
        return
    ui.kpi_cards(cur_t, prev_t, prev_w.label if prev_w else None)

    cur_bd = metrics.breakdown(cur_df, "channel")
    prev_bd = metrics.breakdown(prev_df, "channel") if prev_df is not None else None

    st.markdown('<div class="block-title">Channels</div>', unsafe_allow_html=True)
    ui.channel_cards(cur_bd, prev_bd, brand, theme)

    c1, c2 = st.columns([2, 3], gap="medium")
    with c1:
        st.markdown('<div class="block-title">Channel mix</div>', unsafe_allow_html=True)
        choice = st.segmented_control("Measure", ["Gross sales", "Net sales", "Checks"], default="Gross sales",
                                      key="donut_measure", label_visibility="collapsed") or "Gross sales"
        mkey, mlabel = {"Gross sales": ("sales_gross", "sales before discount"),
                        "Net sales": ("sales_net", "sales after discount"),
                        "Checks": ("checks", "checks")}[choice]
        ui.donut(cur_bd, mkey, mlabel, theme)
    with c2:
        st.markdown('<div class="block-title">Sales after discount by channel</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="block-note">{ {"D": "Daily", "W": "Weekly", "M": "Monthly"}[freq] } buckets'
                    + (" · dotted line = comparison period, aligned to the current dates" if prev_w else "")
                    + "</div>", unsafe_allow_html=True)
        cur_ts = metrics.timeseries(cur_df, "channel", freq)
        prev_ts = metrics.timeseries(prev_df, None, freq, shift) if prev_df is not None else None
        ui.trend(cur_ts, prev_ts, "channel", config.CHANNELS, ui.channel_colors(theme), theme, freq,
                 prev_w.label if prev_w else None)

    st.markdown('<div class="block-title">Breakdown by channel</div>', unsafe_allow_html=True)
    sty = ui.comparison_table(cur_bd, prev_bd, "channel", "Channel")
    if sty is not None:
        st.dataframe(sty, width="stretch", hide_index=True, column_config=ui.table_column_config(sty))

    if brand == "All brands":
        st.markdown('<div class="block-title">Breakdown by brand</div>', unsafe_allow_html=True)
        sty = ui.comparison_table(metrics.breakdown(cur_df, "brand"),
                                  metrics.breakdown(prev_df, "brand") if prev_df is not None else None,
                                  "brand", "Brand")
        if sty is not None:
            st.dataframe(sty, width="stretch", hide_index=True, column_config=ui.table_column_config(sty))

    raw_expander(cur_df, "general")


def render_channel(channel: str, desc: str) -> None:
    ui.section_header(ui.channel_icon(channel, brand, theme), channel, desc)
    c_df = cur_df[cur_df["channel"] == channel]
    p_df = prev_df[prev_df["channel"] == channel] if prev_df is not None else None
    cur_t = metrics.totals(c_df)
    if not cur_t["has_data"]:
        has_any = not df_brand[df_brand["channel"] == channel].empty
        ui.empty_state(f"No {channel} records for {cur_w.label}."
                       + ("" if has_any else f" This brand has no {channel} data in the files."))
        return
    prev_t = metrics.totals(p_df) if p_df is not None else None
    ui.kpi_cards(cur_t, prev_t, prev_w.label if prev_w else None)

    measure = "sales_gross" if channel == "Compliments" else "sales_net"
    m_label = "menu value (before discount)" if channel == "Compliments" else "sales after discount"
    cur_bd = metrics.breakdown(c_df, "payment_label")
    prev_bd = metrics.breakdown(p_df, "payment_label") if p_df is not None else None

    c1, c2 = st.columns([3, 2], gap="medium")
    with c1:
        st.markdown(f'<div class="block-title">Trend · {m_label}</div>', unsafe_allow_html=True)
        labels = cur_bd["payment_label"].tolist()
        colors = dict(zip(labels, tints(len(labels))))
        cur_ts = metrics.timeseries(c_df, "payment_label", freq).rename(columns={measure: "_m"})
        cur_ts["sales_net"] = cur_ts["_m"]
        prev_ts = None
        if p_df is not None:
            prev_ts = metrics.timeseries(p_df, None, freq, shift)
            prev_ts["sales_net"] = prev_ts[measure]
        ui.trend(cur_ts, prev_ts, "payment_label", labels, colors, theme, freq, prev_w.label if prev_w else None)
    with c2:
        st.markdown('<div class="block-title">By payment type</div>', unsafe_allow_html=True)
        ui.payment_bars(cur_bd, prev_bd, theme, measure)

    st.markdown('<div class="block-title">Breakdown by payment type</div>', unsafe_allow_html=True)
    sty = ui.comparison_table(cur_bd, prev_bd, "payment_label", "Payment type")
    if sty is not None:
        st.dataframe(sty, width="stretch", hide_index=True, column_config=ui.table_column_config(sty))
    raw_expander(c_df, channel)


tabs = st.tabs([name for name, _, _ in TABS])
with tabs[0]:
    render_general()
for tab, (name, ch, desc) in zip(tabs[1:], TABS[1:]):
    with tab:
        render_channel(ch, desc)

st.caption(
    "AOV = sales after discount ÷ checks · COGS % = COGS ÷ sales after discount · "
    "Checks are iiko order counts per payment type (an order split across two payment types counts in both). "
    f"Comparison basis: {basis.lower() if compare_on else 'off'}."
)

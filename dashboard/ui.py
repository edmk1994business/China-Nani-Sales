"""Presentation layer: CSS theming, logos, KPI cards, charts and tables."""
from __future__ import annotations

import base64
import html
from functools import lru_cache

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import config
from .metrics import KPIS, delta

CURRENCY = "֏"

GIFT_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<rect width='64' height='64' rx='14' fill='{bg}'/>"
    "<g fill='none' stroke='{fg}' stroke-width='4' stroke-linejoin='round'>"
    "<rect x='14' y='28' width='36' height='22' rx='2'/><rect x='11' y='20' width='42' height='9' rx='2'/>"
    "<path d='M32 20v30'/><path d='M32 20c-4-8-14-8-12-1 1 3 7 2 12 1zM32 20c4-8 14-8 12-1-1 3-7 2-12 1z'/>"
    "</g></svg>"
)
STORE_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<rect width='64' height='64' rx='14' fill='{bg}'/>"
    "<g fill='none' stroke='{fg}' stroke-width='4' stroke-linejoin='round' stroke-linecap='round'>"
    "<path d='M12 26l4-12h32l4 12'/><path d='M12 26c0 4 3 6 6.7 6s6.6-2 6.6-6c0 4 3 6 6.7 6s6.7-2 6.7-6"
    "c0 4 3 6 6.6 6S52 30 52 26'/><path d='M16 32v18h32V32'/><path d='M27 50V39h10v11'/></g></svg>"
)
ALL_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<rect width='64' height='64' rx='14' fill='{bg}'/>"
    "<g fill='{fg}'><rect x='14' y='34' width='8' height='16' rx='2'/><rect x='28' y='24' width='8' height='26' rx='2'/>"
    "<rect x='42' y='14' width='8' height='36' rx='2'/></g></svg>"
)


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
def fmt_money(v, compact=True) -> str:
    if v is None or pd.isna(v):
        return "—"
    a = abs(v)
    if compact and a >= 1e9:
        return f"{v / 1e9:,.2f}B {CURRENCY}"
    if compact and a >= 1e8:
        return f"{v / 1e6:,.1f}M {CURRENCY}"
    if compact and a >= 1e6:
        return f"{v / 1e6:,.2f}M {CURRENCY}"
    if compact and a >= 1e5:
        return f"{v / 1e3:,.1f}K {CURRENCY}"
    return f"{v:,.0f} {CURRENCY}"


def fmt_value(v, kind: str, compact=True) -> str:
    if v is None or pd.isna(v):
        return "—"
    if kind == "money":
        return fmt_money(v, compact)
    if kind == "pct":
        return f"{v * 100:.1f}%"
    return f"{v:,.0f}"


def fmt_delta(d, rel, kind: str) -> str:
    if d is None:
        return "n/a"
    if kind == "pct":
        return f"{d * 100:+.1f} pp"
    if rel is None:
        return "new" if d > 0 else "—"
    return f"{rel * 100:+.1f}%"


# --------------------------------------------------------------------------- #
# Logos
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=32)
def logo_uri(key: str) -> str:
    fname = config.LOGOS.get(key)
    if not fname or not (config.ASSETS / fname).exists():
        return ""
    data = (config.ASSETS / fname).read_bytes()
    mime = "image/png" if fname.endswith(".png") else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def svg_uri(template: str, bg: str, fg: str) -> str:
    svg = template.format(bg=bg, fg=fg)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def channel_icon(channel: str, brand: str, theme: dict) -> str:
    if channel == "Yandex":
        return logo_uri("Yandex_icon")
    if channel in ("Glovo", "Buy.am"):
        return logo_uri(channel)
    if channel == "Compliments":
        return svg_uri(GIFT_SVG, theme["accent_soft"], theme["accent_strong"])
    if channel == "Hall":
        return svg_uri(STORE_SVG, theme["accent_soft"], theme["accent_strong"])
    return ""


def brand_icon(brand: str, theme: dict) -> str:
    if brand in ("ChinaTown", "Nani"):
        return logo_uri(brand)
    return svg_uri(ALL_SVG, theme["accent_soft"], theme["accent_strong"])


def channel_colors(theme: dict) -> dict:
    return {"Hall": theme["hall"], **config.CHANNEL_COLORS}


# --------------------------------------------------------------------------- #
# CSS
# --------------------------------------------------------------------------- #
def inject_css(theme: dict, tab_icons: list[str]) -> None:
    t = theme
    icon_rules = "\n".join(
        f'[role="tablist"] > [role="tab"]:nth-child({i + 1})::before'
        f"{{background-image:url('{uri}');}}"
        for i, uri in enumerate(tab_icons) if uri
    )
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {{
  --accent:{t['accent']}; --accent-strong:{t['accent_strong']}; --accent-soft:{t['accent_soft']};
  --bg:{t['bg']}; --surface:{t['surface']}; --border:{t['border']};
  --text:{t['text']}; --muted:{t['muted']};
  --pos:{config.POSITIVE}; --neg:{config.NEGATIVE};
  --pos-soft:{config.POSITIVE_SOFT}; --neg-soft:{config.NEGATIVE_SOFT};
}}
html, body, .stApp, [data-testid="stMarkdownContainer"], button, input, label {{
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
}}
.stApp {{ background: var(--bg); color: var(--text); }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1440px; }}
section[data-testid="stSidebar"] {{ background: var(--surface); border-right: 1px solid var(--border); }}
section[data-testid="stSidebar"] .sb-title {{
  font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); margin: 14px 0 4px;
}}
h1, h2, h3, h4 {{ color: var(--text); letter-spacing: -0.01em; }}

/* ---------- hero ---------- */
.hero {{
  display:flex; align-items:center; justify-content:space-between; gap:20px; flex-wrap:wrap;
  background: linear-gradient(120deg, {t['hero_from']} 0%, {t['hero_to']} 100%);
  border: 1px solid var(--border); border-radius: 18px; padding: 18px 22px; margin-bottom: 18px;
  box-shadow: 0 1px 2px rgba(16,24,40,.04);
}}
.hero-left {{ display:flex; align-items:center; gap:16px; min-width: 0; }}
.hero-logo {{ width:64px; height:64px; border-radius:14px; object-fit:cover;
  border:1px solid var(--border); background:#fff; flex-shrink:0; }}
.hero h1 {{ font-size: 26px; font-weight: 800; margin: 0; padding: 0; line-height: 1.15; }}
.hero .sub {{ color: var(--muted); font-size: 14px; margin-top: 4px; }}
.hero .sub b {{ color: var(--text); font-weight: 600; }}
.hero-right {{ display:flex; flex-direction:column; align-items:flex-end; gap:10px; }}
.partners {{ display:flex; gap:8px; }}
.partners img {{ width:34px; height:34px; border-radius:9px; border:1px solid var(--border); object-fit:cover; background:#fff; }}
.pill {{ display:inline-flex; align-items:center; gap:6px; font-size:12px; font-weight:600;
  padding:5px 10px; border-radius:999px; background: var(--surface); border:1px solid var(--border); color: var(--muted); }}
.pill .dot {{ width:7px; height:7px; border-radius:50%; background: var(--pos); }}

/* ---------- section header inside tabs ---------- */
.sec-head {{ display:flex; align-items:center; gap:12px; margin: 6px 0 14px; }}
.sec-head img {{ width:40px; height:40px; border-radius:10px; border:1px solid var(--border); object-fit:cover; background:#fff; }}
.sec-head .t {{ font-size: 19px; font-weight: 750; color: var(--text); }}
.sec-head .d {{ font-size: 13px; color: var(--muted); }}
.block-title {{ font-size: 15px; font-weight: 700; color: var(--text); margin: 18px 0 6px; }}
.block-note {{ font-size: 12px; color: var(--muted); margin-top: -2px; margin-bottom: 6px; }}

/* ---------- KPI cards ---------- */
.kpi-grid {{ display:grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap: 12px; margin-bottom: 8px; }}
@media (max-width: 1200px) {{ .kpi-grid {{ grid-template-columns: repeat(3, minmax(0,1fr)); }} }}
@media (max-width: 640px)  {{ .kpi-grid {{ grid-template-columns: repeat(2, minmax(0,1fr)); }} }}
.kpi {{ background: var(--surface); border: 1px solid var(--border); border-top: 3px solid var(--accent);
  border-radius: 14px; padding: 14px 16px 12px; box-shadow: 0 1px 2px rgba(16,24,40,.04); min-width:0; }}
.kpi .label {{ font-size: 11px; font-weight: 650; letter-spacing: .05em; text-transform: uppercase; color: var(--muted);
  line-height: 1.3; min-height: 2.6em; }}
.kpi .value {{ font-size: clamp(17px, 1.45vw, 25px); font-weight: 800; color: var(--text); margin-top: 6px; line-height:1.1;
  font-variant-numeric: tabular-nums; white-space: nowrap; overflow:hidden; text-overflow:ellipsis; }}
.kpi .foot {{ display:flex; align-items:center; gap:8px; margin-top: 8px; flex-wrap: wrap; min-height: 22px; }}
.delta {{ font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 999px; font-variant-numeric: tabular-nums; }}
.delta.good {{ color: var(--pos); background: var(--pos-soft); }}
.delta.bad  {{ color: var(--neg); background: var(--neg-soft); }}
.delta.flat {{ color: var(--muted); background: #F1F3F5; }}
.kpi .prev {{ font-size: 11.5px; color: var(--muted); white-space: nowrap; overflow:hidden; text-overflow:ellipsis; }}

/* ---------- channel cards ---------- */
.ch-grid {{ display:grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 12px; }}
@media (max-width: 1200px) {{ .ch-grid {{ grid-template-columns: repeat(3, minmax(0,1fr)); }} }}
@media (max-width: 640px)  {{ .ch-grid {{ grid-template-columns: repeat(2, minmax(0,1fr)); }} }}
.ch {{ background: var(--surface); border:1px solid var(--border); border-radius: 14px; padding: 14px; min-width:0; }}
.ch-top {{ display:flex; align-items:center; gap:10px; }}
.ch-top img {{ width:34px; height:34px; border-radius:9px; border:1px solid var(--border); object-fit:cover; background:#fff; }}
.ch-top .n {{ font-weight: 700; font-size: 14px; color: var(--text); }}
.ch-top .s {{ font-size: 12px; color: var(--muted); }}
.ch .v {{ font-size: clamp(17px, 1.35vw, 21px); font-weight: 800; margin-top: 10px; font-variant-numeric: tabular-nums; color: var(--text); }}
.ch .bar {{ height: 6px; background: #EEF0F3; border-radius: 99px; margin: 8px 0 8px; overflow:hidden; }}
.ch .bar > div {{ height: 100%; border-radius: 99px; }}
.ch .meta {{ display:flex; justify-content:space-between; align-items:center; font-size: 12px; color: var(--muted); gap:6px; }}

/* ---------- tabs with logos (works for both old baseweb and new react-aria tabs) ---------- */
[role="tablist"] {{ gap: 6px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }}
[role="tablist"] > [role="tab"] {{
  display:inline-flex; align-items:center; gap: 8px; height: 46px; padding: 0 16px 0 10px; margin: 0;
  background: var(--surface); border: 1px solid var(--border); border-bottom: none;
  border-radius: 12px 12px 0 0; color: var(--muted); position: relative;
}}
[role="tablist"] > [role="tab"] p {{ font-size: 14px; font-weight: 650; margin: 0; }}
[role="tablist"] > [role="tab"]::before {{
  content:""; width: 26px; height: 26px; border-radius: 7px; background-size: cover; background-position:center;
  border: 1px solid var(--border); flex-shrink:0; background-color:#fff;
}}
[role="tablist"] > [role="tab"][aria-selected="true"] {{ background: var(--accent-soft); color: var(--accent-strong); }}
[role="tablist"] > [role="tab"][aria-selected="true"] p {{ color: var(--accent-strong); }}
[data-baseweb="tab-highlight"], .react-aria-SelectionIndicator {{ background-color: var(--accent) !important; height: 3px !important; }}
[data-baseweb="tab-border"] {{ display:none; }}
{icon_rules}

/* ---------- misc ---------- */
[data-testid="stExpander"] details {{ background: var(--surface); border:1px solid var(--border); border-radius: 12px; }}
[data-testid="stDataFrame"] {{ border:1px solid var(--border); border-radius: 12px; overflow:hidden; }}
div[data-testid="stPlotlyChart"] {{ background: var(--surface); border:1px solid var(--border); border-radius: 14px; padding: 6px 6px 0; }}
.empty {{ background: var(--surface); border:1px dashed var(--border); border-radius: 14px; padding: 28px; text-align:center; color: var(--muted); }}
</style>
""",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Blocks
# --------------------------------------------------------------------------- #
def hero(brand: str, theme: dict, period_label: str, compare_label: str | None,
         data_through: str, fetched_at: str) -> None:
    title = "All Brands" if brand == "All brands" else brand
    cmp_html = f" &nbsp;·&nbsp; vs <b>{html.escape(compare_label)}</b>" if compare_label else ""
    partners = "".join(
        f'<img src="{logo_uri(k)}" title="{n}"/>'
        for k, n in (("Yandex_icon", "Yandex Eats"), ("Glovo", "Glovo"), ("Buy.am", "Buy.am"))
    )
    if brand == "All brands":
        logos = (f'<img class="hero-logo" src="{logo_uri("ChinaTown")}"/>'
                 f'<img class="hero-logo" src="{logo_uri("Nani")}" style="margin-left:-12px"/>')
    else:
        logos = f'<img class="hero-logo" src="{brand_icon(brand, theme)}"/>'
    st.markdown(
        f"""
<div class="hero">
  <div class="hero-left">
    <div style="display:flex">{logos}</div>
    <div>
      <h1>{html.escape(title)} · Sales Performance</h1>
      <div class="sub"><b>{html.escape(period_label)}</b>{cmp_html}</div>
    </div>
  </div>
  <div class="hero-right">
    <div class="partners">{partners}</div>
    <span class="pill"><span class="dot"></span>Data through {html.escape(data_through)} · refreshed {html.escape(fetched_at)}</span>
  </div>
</div>""",
        unsafe_allow_html=True,
    )


def section_header(icon_uri: str, title: str, desc: str) -> None:
    img = f'<img src="{icon_uri}"/>' if icon_uri else ""
    st.markdown(
        f'<div class="sec-head">{img}<div><div class="t">{html.escape(title)}</div>'
        f'<div class="d">{html.escape(desc)}</div></div></div>',
        unsafe_allow_html=True,
    )


def _delta_class(d, kind: str, higher_is_better: bool) -> str:
    if d is None or abs(d) < (0.0005 if kind == "pct" else 1e-9):
        return "flat"
    good = (d > 0) == higher_is_better
    return "good" if good else "bad"


def kpi_cards(cur: dict, prev: dict | None, compare_label: str | None) -> None:
    cards = []
    for k in KPIS:
        v = cur.get(k.key)
        value = fmt_value(v, k.kind)
        full = fmt_value(v, k.kind, compact=False)
        foot = ""
        if prev is not None:
            pv = prev.get(k.key)
            d, rel = delta(v, pv, k.kind)
            cls = _delta_class(d, k.kind, k.higher_is_better)
            arrow = "▲" if d and d > 0 else ("▼" if d and d < 0 else "")
            foot = (f'<span class="delta {cls}">{arrow} {fmt_delta(d, rel, k.kind)}</span>'
                    f'<span class="prev" title="{html.escape(compare_label or "")}">prev {fmt_value(pv, k.kind)}</span>')
        cards.append(
            f'<div class="kpi" title="{html.escape(full)}"><div class="label">{k.label}</div>'
            f'<div class="value">{value}</div><div class="foot">{foot}</div></div>'
        )
    st.markdown(f'<div class="kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def channel_cards(cur_bd: pd.DataFrame, prev_bd: pd.DataFrame | None, brand: str, theme: dict) -> None:
    colors = channel_colors(theme)
    total_net = cur_bd["sales_net"].sum() if not cur_bd.empty else 0
    cur_i = cur_bd.set_index("channel") if not cur_bd.empty else pd.DataFrame()
    prev_i = prev_bd.set_index("channel") if prev_bd is not None and not prev_bd.empty else None
    out = []
    for ch in config.CHANNELS:
        row = cur_i.loc[ch] if ch in cur_i.index else None
        net = float(row["sales_net"]) if row is not None else 0.0
        gross = float(row["sales_gross"]) if row is not None else 0.0
        checks = float(row["checks"]) if row is not None else 0.0
        if ch == "Compliments":
            main, share, sub = fmt_money(gross), (gross / cur_bd["sales_gross"].sum() if gross else 0), "value given (menu price)"
            metric_key, cur_v = "sales_gross", gross
        else:
            main, share, sub = fmt_money(net), (net / total_net if total_net else 0), "sales after discount"
            metric_key, cur_v = "sales_net", net
        badge = ""
        if prev_i is not None:
            pv = float(prev_i.loc[ch, metric_key]) if ch in prev_i.index else 0.0
            d, rel = delta(cur_v, pv, "money")
            cls = _delta_class(d, "money", ch != "Compliments")
            badge = f'<span class="delta {cls}">{fmt_delta(d, rel, "money")}</span>'
        out.append(
            f'<div class="ch"><div class="ch-top"><img src="{channel_icon(ch, brand, theme)}"/>'
            f'<div><div class="n">{ch}</div><div class="s">{sub}</div></div></div>'
            f'<div class="v">{main}</div>'
            f'<div class="bar"><div style="width:{min(share, 1) * 100:.1f}%;background:{colors[ch]}"></div></div>'
            f'<div class="meta"><span>{share * 100:.1f}% share · {checks:,.0f} checks</span>{badge}</div></div>'
        )
    st.markdown(f'<div class="ch-grid">{"".join(out)}</div>', unsafe_allow_html=True)


def empty_state(msg: str) -> None:
    st.markdown(f'<div class="empty">{html.escape(msg)}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
PLOT_CFG = {"displayModeBar": False, "responsive": True}


def _layout(fig: go.Figure, theme: dict, height: int) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=12, r=12, t=16, b=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=12, color=theme["text"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Inter"),
    )
    fig.update_xaxes(showgrid=False, linecolor=theme["border"], tickfont=dict(color=theme["muted"]))
    fig.update_yaxes(gridcolor="#EEF0F3", zeroline=False, tickfont=dict(color=theme["muted"]))
    return fig


def donut(bd: pd.DataFrame, measure: str, measure_label: str, theme: dict) -> None:
    colors = channel_colors(theme)
    d = bd[bd[measure] > 0]
    if d.empty:
        empty_state("No sales in this period.")
        return
    total = d[measure].sum()
    center = fmt_value(total, "count" if measure == "checks" else "money")
    fig = go.Figure(go.Pie(
        labels=d["channel"], values=d[measure], hole=0.64, sort=False,
        marker=dict(colors=[colors.get(c, "#999") for c in d["channel"]], line=dict(color="white", width=2)),
        textinfo="percent", textposition="outside", textfont=dict(size=13),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f}<br>%{percent}<extra></extra>",
        direction="clockwise", rotation=90,
    ))
    fig.add_annotation(text=f"<b style='font-size:20px'>{center}</b><br><span style='font-size:12px;color:{theme['muted']}'>"
                            f"{measure_label}</span>", showarrow=False, x=0.5, y=0.5)
    _layout(fig, theme, 380)
    fig.update_layout(legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center", yanchor="top"),
                      margin=dict(l=48, r=48, t=30, b=30))
    st.plotly_chart(fig, width="stretch", config=PLOT_CFG)


def trend(cur_ts: pd.DataFrame, prev_ts: pd.DataFrame | None, by: str, order: list[str],
          colors: dict, theme: dict, freq: str, prev_label: str | None) -> None:
    if cur_ts.empty:
        empty_state("No sales in this period.")
        return
    fig = go.Figure()
    for name in order:
        part = cur_ts[cur_ts[by] == name]
        if part.empty or part["sales_net"].sum() == 0:
            continue
        fig.add_bar(x=part["bucket"], y=part["sales_net"], name=name, marker_color=colors.get(name),
                    hovertemplate=f"<b>{name}</b><br>%{{x|%d %b %Y}}<br>%{{y:,.0f}} {CURRENCY}<extra></extra>")
    if prev_ts is not None and not prev_ts.empty:
        p = prev_ts.groupby("bucket", as_index=False)["sales_net"].sum()
        fig.add_scatter(x=p["bucket"], y=p["sales_net"], name=f"Comparison ({prev_label})", mode="lines+markers",
                        line=dict(color=theme["text"], width=2, dash="dot"), marker=dict(size=5),
                        hovertemplate=f"<b>Comparison</b><br>%{{y:,.0f}} {CURRENCY}<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.25)
    tick = {"D": "%d %b", "W": "%d %b", "M": "%b %Y"}[freq]
    fig.update_xaxes(tickformat=tick)
    fig.update_yaxes(tickformat="~s")
    st.plotly_chart(_layout(fig, theme, 360), width="stretch", config=PLOT_CFG)


def payment_bars(cur_bd: pd.DataFrame, prev_bd: pd.DataFrame | None, theme: dict, measure="sales_net") -> None:
    if cur_bd.empty:
        empty_state("No sales in this period.")
        return
    d = cur_bd.sort_values(measure)
    fig = go.Figure()
    if prev_bd is not None and not prev_bd.empty:
        p = prev_bd.set_index("payment_label")[measure].reindex(d["payment_label"]).fillna(0)
        fig.add_bar(y=d["payment_label"], x=p.values, orientation="h", name="Comparison",
                    marker_color="#CBD2DA", hovertemplate=f"%{{x:,.0f}} {CURRENCY}<extra>Comparison</extra>")
    fig.add_bar(y=d["payment_label"], x=d[measure], orientation="h", name="Current",
                marker_color=theme["accent"], text=[fmt_money(v) for v in d[measure]], textposition="outside",
                cliponaxis=False, hovertemplate=f"%{{x:,.0f}} {CURRENCY}<extra>Current</extra>")
    fig.update_layout(barmode="group", bargap=0.3)
    xmax = max(d[measure].max(), p.max() if prev_bd is not None and not prev_bd.empty else 0)
    fig.update_xaxes(tickformat="~s", gridcolor="#EEF0F3", showgrid=True, range=[0, xmax * 1.25 or 1])
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(_layout(fig, theme, max(240, 60 + 46 * len(d))), width="stretch", config=PLOT_CFG)


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
def comparison_table(cur_bd: pd.DataFrame, prev_bd: pd.DataFrame | None, key: str, key_label: str):
    """Breakdown table with a total row; adds variance columns when prev_bd is given."""
    def with_total(bd):
        if bd.empty:
            return bd
        tot = bd[["sales_gross", "sales_net", "checks", "cogs"]].sum()
        tot[key] = "Total"
        tot["aov"] = tot["sales_net"] / tot["checks"] if tot["checks"] else None
        tot["cogs_pct"] = tot["cogs"] / tot["sales_net"] if tot["sales_net"] else None
        return pd.concat([bd, tot.to_frame().T], ignore_index=True)

    cur = with_total(cur_bd)
    if cur.empty:
        return None
    t = pd.DataFrame({
        key_label: cur[key],
        "Sales before disc.": cur["sales_gross"].astype(float),
        "Sales after disc.": cur["sales_net"].astype(float),
        "Checks": cur["checks"].astype(float),
        "AOV": pd.to_numeric(cur["aov"], errors="coerce"),
        "COGS": cur["cogs"].astype(float),
        "COGS %": pd.to_numeric(cur["cogs_pct"], errors="coerce"),
    })
    var_cols = []
    if prev_bd is not None:
        prev = with_total(prev_bd)
        p = prev.set_index(key) if not prev.empty else pd.DataFrame(columns=["sales_net", "checks", "cogs_pct"])
        ps = pd.to_numeric(p["sales_net"], errors="coerce").reindex(cur[key]).values
        pc = pd.to_numeric(p["checks"], errors="coerce").reindex(cur[key]).values
        pp = pd.to_numeric(p["cogs_pct"], errors="coerce").reindex(cur[key]).values
        t["Prev sales after disc."] = ps
        t["Δ Sales"] = t["Sales after disc."] - t["Prev sales after disc."]
        t["Δ Sales %"] = t["Δ Sales"] / t["Prev sales after disc."].where(t["Prev sales after disc."] != 0)
        t["Δ Checks %"] = (t["Checks"] - pc) / pd.Series(pc).where(pd.Series(pc) != 0).values
        t["Δ COGS % (pp)"] = (t["COGS %"] - pp) * 100
        var_cols = ["Δ Sales", "Δ Sales %", "Δ Checks %", "Δ COGS % (pp)"]

    money = lambda v: "—" if pd.isna(v) else f"{v:,.0f}"
    fmt = {
        "Sales before disc.": money, "Sales after disc.": money, "AOV": money, "COGS": money,
        "Checks": lambda v: "—" if pd.isna(v) else f"{v:,.0f}",
        "COGS %": lambda v: "—" if pd.isna(v) else f"{v * 100:.1f}%",
    }
    if var_cols:
        fmt.update({
            "Prev sales after disc.": money,
            "Δ Sales": lambda v: "—" if pd.isna(v) else f"{v:+,.0f}",
            "Δ Sales %": lambda v: "—" if pd.isna(v) else f"{v * 100:+.1f}%",
            "Δ Checks %": lambda v: "—" if pd.isna(v) else f"{v * 100:+.1f}%",
            "Δ COGS % (pp)": lambda v: "—" if pd.isna(v) else f"{v:+.1f} pp",
        })

    def color(v, invert=False):
        if pd.isna(v) or v == 0:
            return ""
        good = (v > 0) != invert
        c, bg = (config.POSITIVE, config.POSITIVE_SOFT) if good else (config.NEGATIVE, config.NEGATIVE_SOFT)
        return f"color:{c}; background-color:{bg}; font-weight:600"

    # Render pre-formatted strings (Streamlit shows nulls as "None" otherwise) and
    # colour them from the numeric frame.
    disp = t.copy()
    for col, f in fmt.items():
        disp[col] = t[col].map(f)
    disp[key_label] = t[key_label].astype(str)

    def styles(_):
        css = pd.DataFrame("text-align:right", index=t.index, columns=t.columns)
        css[key_label] = "text-align:left"
        for col in var_cols:
            css[col] = css[col] + ";" + t[col].map(lambda v, c=col: color(v, invert=(c == "Δ COGS % (pp)")))
        css.iloc[-1] = css.iloc[-1] + "; font-weight:700"
        return css

    return disp.style.apply(styles, axis=None).hide(axis="index")


def table_column_config(sty) -> dict:
    """Pixel widths so long numbers are never clipped."""
    widths = {"Checks": 80, "AOV": 80, "COGS %": 80, "Δ Sales %": 95, "Δ Checks %": 100, "Δ COGS % (pp)": 115,
              "Channel": 120, "Brand": 120, "Payment type": 190}
    return {c: st.column_config.TextColumn(c, width=widths.get(c, 125)) for c in sty.data.columns}


def raw_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values(["date", "brand", "channel", "payment_label"], ascending=[False, True, True, True]).copy()
    out["aov"] = (out["sales_net"] / out["checks"]).where(out["checks"] > 0)
    out["cogs_pct"] = ((out["cogs"] / out["sales_net"]).where(out["sales_net"] > 0) * 100).round(1)
    for c in ("sales_gross", "sales_net", "aov", "cogs"):
        out[c] = out[c].round(0)
    out["checks"] = out["checks"].round(1)
    return out.rename(columns={
        "date": "Date", "brand": "Brand", "channel": "Channel", "payment_label": "Payment type",
        "payment_type": "Payment type (iiko)", "sales_gross": "Sales before disc.", "sales_net": "Sales after disc.",
        "checks": "Checks", "aov": "AOV", "cogs": "COGS", "cogs_pct": "COGS %",
    })[["Date", "Brand", "Channel", "Payment type", "Payment type (iiko)", "Sales before disc.",
        "Sales after disc.", "Checks", "AOV", "COGS", "COGS %"]]


RAW_COLUMN_CONFIG = {
    "Date": st.column_config.DateColumn(format="DD MMM YYYY"),
    "Sales before disc.": st.column_config.NumberColumn(format="localized"),
    "Sales after disc.": st.column_config.NumberColumn(format="localized"),
    "Checks": st.column_config.NumberColumn(format="localized"),
    "AOV": st.column_config.NumberColumn(format="localized"),
    "COGS": st.column_config.NumberColumn(format="localized"),
    "COGS %": st.column_config.NumberColumn(format="%.1f%%"),
}

"""Presentation layer: CSS theming, logos, navigation, KPI cards, charts and tables."""
from __future__ import annotations

import base64
import html
from functools import lru_cache

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from . import config
from .metrics import KPIS, delta

CURRENCY = "֏"
SECTIONS = ["General", "Hall", "Yandex", "Glovo", "Buy.am", "Compliments"]
SECTION_DESC = {
    "General": "All channels combined",
    "Hall": "Dine-in & direct sales: cash, cards, Idram, transfers",
    "Yandex": "Yandex Eats delivery",
    "Glovo": "Glovo delivery",
    "Buy.am": "Buy.am delivery",
    "Compliments": "Orders closed without payment (compliments / promo)",
}
COST_KPIS = {"cogs", "cogs_pct"}

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


def slug(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


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


def _delta_class(d, kind: str, higher_is_better: bool) -> str:
    if d is None or pd.isna(d) or abs(d) < (0.0005 if kind == "pct" else 1e-9):
        return "flat"
    return "good" if (d > 0) == higher_is_better else "bad"


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


def section_icon(section: str, brand: str, theme: dict) -> str:
    return brand_icon(brand, theme) if section == "General" else channel_icon(section, brand, theme)


def channel_colors(theme: dict) -> dict:
    return {"Hall": theme["hall"], **config.CHANNEL_COLORS}


def tints(theme: dict, n: int) -> list[str]:
    """n distinguishable shades of the brand accent (for payment-type series)."""
    out = []
    for i in range(n):
        src = (theme["accent_strong"] if i == 0 else theme["accent"]).lstrip("#")
        mix = 0 if i < 2 else min(0.2 * (i - 1), 0.75)
        r, g, b = (int(src[j:j + 2], 16) for j in (0, 2, 4))
        r, g, b = (int(c + (255 - c) * mix) for c in (r, g, b))
        out.append(f"#{r:02x}{g:02x}{b:02x}")
    return out


# --------------------------------------------------------------------------- #
# CSS
# --------------------------------------------------------------------------- #
def _on_color(hex_color: str) -> str:
    """Readable text colour on top of a brand colour (dark text on gold, white on red/slate)."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return "#2A1A00" if lum > 0.35 else "#FFFFFF"


def inject_css(theme: dict, brand: str) -> None:
    t = theme
    on_accent = _on_color(t["accent"])
    nav_icons = "\n".join(
        f'.st-key-nav [data-testid="stRadioGroup"] > div:nth-child({i + 1}) [data-testid="stRadioOption"]::before'
        f"{{background-image:url('{section_icon(s, brand, theme)}');}}"
        for i, s in enumerate(SECTIONS)
    )
    brand_icons = "\n".join(
        f'.st-key-pill_brand [data-testid="stRadioGroup"] > div:nth-child({i + 1}) [data-testid="stRadioOption"]::before'
        f"{{background-image:url('{brand_icon(b, config.THEMES[b])}');}}"
        for i, b in enumerate(config.BRANDS)
    )
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {{
  --accent:{t['accent']}; --accent-strong:{t['accent_strong']}; --accent-soft:{t['accent_soft']};
  --on-accent:{on_accent};
  --bg:{t['bg']}; --surface:{t['surface']}; --border:{t['border']};
  --text:{t['text']}; --muted:{t['muted']};
  --pos:{config.POSITIVE}; --neg:{config.NEGATIVE};
  --pos-soft:{config.POSITIVE_SOFT}; --neg-soft:{config.NEGATIVE_SOFT};
  --shadow: 0 1px 2px rgba(16,24,40,.05);
}}
html, body, .stApp, [data-testid="stMarkdownContainer"], button, input, label, table {{
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
}}

/* ===== 1. no horizontal page scrolling / side gaps on any screen ===== */
/* 'clip' (not 'hidden') stops sideways overflow without creating extra scroll containers */
html, body {{ overflow-x: hidden !important; max-width: 100vw !important; }}
.stApp, [data-testid="stAppViewContainer"] {{ overflow-x: clip !important; max-width: 100vw !important; }}
[data-testid="stMain"] {{ overflow-x: hidden !important; max-width: 100vw !important; }}   /* the page's own scroller */
.block-container, [data-testid="stMainBlockContainer"] {{
  max-width: min(1440px, 100vw) !important; overflow-x: clip !important; box-sizing: border-box; }}
/* (columns keep Streamlit's own min-width so they still stack on phones) */
[data-testid="stVerticalBlock"], [data-testid="stHorizontalBlock"],
[data-testid="stElementContainer"], [data-testid="stMarkdownContainer"] {{ max-width: 100%; min-width: 0; }}
[data-testid="stColumn"] {{ max-width: 100%; }}
img, svg, canvas, iframe, .js-plotly-plot, .plot-container, .svg-container {{ max-width: 100% !important; }}
[role="radiogroup"], [data-testid="stRadioGroup"] {{ max-width: 100%; }}

/* ===== 3. hide Streamlit / GitHub chrome (keep only the sidebar opener) ===== */
[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"], [data-testid="stMainMenu"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"], #MainMenu, footer, [data-testid="stFooter"],
.stDeployButton, [class*="viewerBadge"], [class*="profileContainer"], [data-testid="manage-app-button"],
a[href*="github.com"][target="_blank"][class*="toolbar"] {{ display: none !important; visibility: hidden !important; }}
header[data-testid="stHeader"] {{ background: transparent !important; box-shadow: none !important; pointer-events: none; }}
header[data-testid="stHeader"] [data-testid="stExpandSidebarButton"] {{ pointer-events: auto; }}
[data-testid="stExpandSidebarButton"] {{
  background: var(--accent) !important; color: var(--on-accent) !important; border-radius: 12px !important;
  box-shadow: 0 4px 14px rgba(16,24,40,.18); padding: 6px 12px 6px 8px !important; width: auto !important; gap: 4px; }}
[data-testid="stExpandSidebarButton"] span, [data-testid="stExpandSidebarButton"] svg {{ color: var(--on-accent) !important; }}
[data-testid="stExpandSidebarButton"]::after {{ content: "Filters"; font-weight: 700; font-size: 14px; }}

.stApp {{ background: var(--bg); color: var(--text); }}
.block-container {{ padding-top: 1.6rem !important; padding-bottom: 3rem; }}
h1, h2, h3, h4 {{ color: var(--text); letter-spacing: -0.01em; }}
a, a:visited {{ color: var(--accent-strong); }}

/* ===== brand palette on native widgets ===== */
[data-testid="stCheckbox"] label[data-selected="true"] > span + div {{ background-color: var(--accent) !important; }}
[data-testid="stRadioOption"][data-selected="true"] > div > div:first-child {{
  background-color: var(--accent) !important; border-color: var(--accent) !important; }}
[data-testid="stRadioOption"]:hover > div > div:first-child {{ border-color: var(--accent) !important; }}
[data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button {{
  border-color: var(--border) !important; background: var(--surface) !important; color: var(--text) !important; }}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stDownloadButton"] button:hover,
[data-testid="stBaseButton-secondary"]:focus-visible {{
  border-color: var(--accent) !important; color: var(--accent-strong) !important; background: var(--accent-soft) !important; }}
[data-testid="stBaseButton-primary"] {{ background: var(--accent) !important; border-color: var(--accent) !important; color: var(--on-accent) !important; }}
.stSelectbox [role="group"]:focus-within, [data-testid="stDateInputField"]:focus-within,
.stSelectbox [role="group"]:hover, [data-testid="stDateInputField"]:hover {{ border-color: var(--accent) !important; }}
[data-testid="stExpander"] summary:hover, [data-testid="stExpander"] summary:hover p {{ color: var(--accent-strong) !important; }}

/* ===== 8. sidebar: numbered section cards + pill options ===== */
section[data-testid="stSidebar"] {{ background: var(--bg); border-right: 1px solid var(--border); }}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{ padding-top: .5rem; }}
[class*="st-key-sbsec_"] {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 12px 14px 14px; box-shadow: var(--shadow); gap: .55rem !important; }}
.sb-h {{ display:flex; align-items:center; gap:9px; font-size: 14.5px; font-weight: 800; color: var(--text); margin-bottom: 4px; }}
[class*="st-key-pill_"], [class*="st-key-sbsec_"] [data-testid="stElementContainer"] {{ width: 100% !important; }}
.sb-h .n {{ width: 24px; height: 24px; border-radius: 50%; background: var(--accent); color: var(--on-accent);
  display:inline-flex; align-items:center; justify-content:center; font-size: 12.5px; font-weight: 800; flex-shrink:0; }}
.sb-foot {{ font-size: 12px; color: var(--muted); line-height: 1.5; }}

[class*="st-key-pill_"] [data-testid="stRadioGroup"] {{ display:flex; flex-wrap: wrap; gap: 8px !important; }}
[class*="st-key-pill_"] [data-testid="stRadioGroup"] > div {{ margin: 0 !important; }}
[class*="st-key-pill_"] [data-testid="stRadioOption"] {{
  display:inline-flex; align-items:center; gap: 7px; min-height: 38px; padding: 7px 14px; margin: 0 !important;
  background: var(--surface); border: 1.5px solid var(--border); border-radius: 999px; cursor: pointer;
  transition: background .15s, border-color .15s, box-shadow .15s, transform .1s; }}
[class*="st-key-pill_"] [data-testid="stRadioOption"] > div > div:first-child {{ display: none !important; }}
[class*="st-key-pill_"] [data-testid="stRadioOption"] p {{ font-size: 13.5px; font-weight: 650; color: var(--text); margin: 0; white-space: nowrap; }}
[class*="st-key-pill_"] [data-testid="stRadioOption"]:hover {{ border-color: var(--accent); background: var(--accent-soft); }}
[class*="st-key-pill_"] [data-testid="stRadioOption"]:active {{ transform: scale(.97); }}
[class*="st-key-pill_"] [data-testid="stRadioOption"][data-selected="true"] {{
  background: var(--accent); border-color: var(--accent); box-shadow: 0 3px 10px rgba(16,24,40,.15); }}
[class*="st-key-pill_"] [data-testid="stRadioOption"][data-selected="true"] p {{ color: var(--on-accent); font-weight: 750; }}
.st-key-pill_level [data-testid="stRadioGroup"], .st-key-pill_sb_preset [data-testid="stRadioGroup"],
.st-key-pill_basis [data-testid="stRadioGroup"] {{ display:grid !important; gap: 6px !important; }}
.st-key-pill_level [data-testid="stRadioGroup"] {{ grid-template-columns: repeat(3, minmax(0,1fr)); }}
.st-key-pill_sb_preset [data-testid="stRadioGroup"] {{ grid-template-columns: repeat(2, minmax(0,1fr)); }}
.st-key-pill_basis [data-testid="stRadioGroup"] {{ grid-template-columns: 1fr; }}
.st-key-pill_level [data-testid="stRadioGroup"] > div, .st-key-pill_sb_preset [data-testid="stRadioGroup"] > div,
.st-key-pill_basis [data-testid="stRadioGroup"] > div {{ min-width: 0; }}
.st-key-pill_level [data-testid="stRadioOption"], .st-key-pill_sb_preset [data-testid="stRadioOption"],
.st-key-pill_basis [data-testid="stRadioOption"] {{ justify-content: center; width: 100%; padding: 7px 6px; min-height: 40px; }}
.st-key-pill_level [data-testid="stRadioOption"] p, .st-key-pill_sb_preset [data-testid="stRadioOption"] p {{
  font-size: 13px; overflow: hidden; text-overflow: ellipsis; }}
.st-key-pill_brand [data-testid="stRadioGroup"] {{ display:grid; grid-template-columns: 1fr; gap: 6px !important; }}
.st-key-pill_brand [data-testid="stRadioOption"] {{ width: 100%; border-radius: 12px; min-height: 46px; padding: 6px 12px 6px 6px; }}
.st-key-pill_brand [data-testid="stRadioOption"]::before {{
  content:""; width: 32px; height: 32px; border-radius: 8px; background-size: cover; background-position: center;
  background-color: #fff; border: 1px solid var(--border); flex-shrink: 0; }}
{brand_icons}

/* ===== header card: title + date pickers + quick presets ===== */
.st-key-hdr {{
  background: linear-gradient(120deg, {t['hero_from']} 0%, {t['hero_to']} 100%);
  border: 1px solid var(--border); border-top: 4px solid var(--accent); border-radius: 18px;
  padding: 18px 22px 16px; margin-bottom: 6px; box-shadow: var(--shadow); gap: .7rem !important; }}
.hero-left {{ display:flex; align-items:center; gap:16px; min-width: 0; }}
.hero-logo {{ width:60px; height:60px; border-radius:14px; object-fit:cover;
  border:1px solid var(--border); background:#fff; flex-shrink:0; }}
.hero-title h1 {{ font-size: 26px; font-weight: 800; margin: 0; padding: 0; line-height: 1.15; }}
.hero-title .sub {{ color: var(--muted); font-size: 14px; margin-top: 4px; }}
.hero-title .sub b {{ color: var(--text); font-weight: 650; }}
.hero-title .notes {{ display:flex; gap:6px; flex-wrap:wrap; margin-top:8px; }}
.pill {{ display:inline-flex; align-items:center; gap:6px; font-size:12px; font-weight:600; padding:4px 10px;
  border-radius:999px; background: var(--accent-soft); color: var(--accent-strong); }}
.st-key-hdr [data-testid="stDateInput"] label p {{ font-size: 12px; font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: .05em; }}
.st-key-hdr [data-testid="stDateInputField"] {{ background: var(--surface) !important; border-radius: 10px !important; min-height: 42px; }}
.st-key-hdr_row [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; gap: 12px !important; align-items: flex-end; }}
.hdr-label {{ font-size: 12px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 4px; }}

/* ===== section navigation (logo tabs) ===== */
.st-key-nav {{ margin: 6px 0 2px; }}
.st-key-nav [data-testid="stRadioGroup"] {{ gap: 6px !important; flex-wrap: wrap; border-bottom: 2px solid var(--border); }}
.st-key-nav [data-testid="stRadioOption"] {{
  display:inline-flex; align-items:center; gap:8px; height:46px; padding: 0 16px 0 10px; margin: 0 0 -2px 0;
  background: var(--surface); border: 1px solid var(--border); border-bottom: 2px solid var(--border);
  border-radius: 12px 12px 0 0; cursor: pointer; transition: background .15s, color .15s; }}
.st-key-nav [data-testid="stRadioOption"] > div > div:first-child {{ display:none !important; }}
.st-key-nav [data-testid="stRadioOption"] p {{ font-size: 14px; font-weight: 650; color: var(--muted); margin: 0; white-space: nowrap; }}
.st-key-nav [data-testid="stRadioOption"]::before {{
  content:""; width: 26px; height: 26px; border-radius: 7px; background-size: cover; background-position:center;
  border: 1px solid var(--border); flex-shrink:0; background-color:#fff; }}
.st-key-nav [data-testid="stRadioOption"]:hover {{ background: var(--accent-soft); }}
.st-key-nav [data-testid="stRadioOption"][data-selected="true"] {{ background: var(--accent-soft); border-bottom: 3px solid var(--accent); }}
.st-key-nav [data-testid="stRadioOption"][data-selected="true"] p {{ color: var(--accent-strong); }}
{nav_icons}

/* ===== section header ===== */
.sec-head {{ display:flex; align-items:center; gap:12px; margin: 10px 0 14px; }}
.sec-head img {{ width:40px; height:40px; border-radius:10px; border:1px solid var(--border); object-fit:cover; background:#fff; }}
.sec-head .t {{ font-size: 19px; font-weight: 750; color: var(--text); }}
.sec-head .d {{ font-size: 13px; color: var(--muted); }}
.block-title {{ font-size: 15px; font-weight: 700; color: var(--text); margin: 20px 0 6px; }}
.block-note {{ font-size: 12px; color: var(--muted); margin: -2px 0 8px; }}

/* ===== 5 + 7. KPI cards: value, prior value underneath, delta pill on the right ===== */
.kpi-grid {{ display:grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap: 12px; margin-bottom: 8px; }}
@media (max-width: 1200px) {{ .kpi-grid {{ grid-template-columns: repeat(3, minmax(0,1fr)); }} }}
.kpi {{ background: var(--surface); border: 1px solid var(--border); border-top: 3px solid var(--accent);
  border-radius: 14px; padding: 13px 15px 12px; box-shadow: var(--shadow); min-width:0;
  transform-origin: center bottom; will-change: transform; cursor: default; }}
.kpi.cost {{ border-top-style: dashed; }}
.kpi .label {{ font-size: 11px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; color: var(--muted);
  line-height: 1.3; min-height: 2.6em; }}
.kpi .kpi-row {{ display:flex; align-items:center; justify-content:space-between; gap: 6px 8px; flex-wrap: wrap; margin-top: 6px; }}
.kpi .value {{ font-size: clamp(18px, 1.45vw, 25px); font-weight: 800; color: var(--text); line-height:1.1;
  font-variant-numeric: tabular-nums; white-space: nowrap; overflow:hidden; text-overflow:ellipsis; min-width: 0; }}
.kpi .prior {{ font-size: 12px; color: #8A8F98; margin-top: 5px; font-variant-numeric: tabular-nums; line-height: 1.35; }}
.kpi .prior .costtag {{ white-space: nowrap; }}
.delta {{ font-size: 12px; font-weight: 700; padding: 3px 9px; border-radius: 999px; font-variant-numeric: tabular-nums; white-space:nowrap; }}
.delta.good {{ color: var(--pos); background: var(--pos-soft); }}
.delta.bad  {{ color: var(--neg); background: var(--neg-soft); }}
.delta.flat {{ color: var(--muted); background: #F1F3F5; }}
.costtag {{ font-size: 10.5px; font-weight: 700; letter-spacing:.03em; text-transform: uppercase; }}
.costtag.bad {{ color: var(--neg); }} .costtag.good {{ color: var(--pos); }}
@keyframes kpiPulse {{
  0%   {{ transform: translateY(0) scale(1); box-shadow: var(--shadow); }}
  16%  {{ transform: translateY(-5px) scale(1.03); box-shadow: 0 14px 30px rgba(16,24,40,.12), 0 0 0 3px var(--accent-soft); }}
  45%  {{ transform: translateY(-2px) scale(1.012); box-shadow: 0 8px 18px rgba(16,24,40,.09), 0 0 0 2px var(--accent-soft); }}
  100% {{ transform: translateY(0) scale(1); box-shadow: var(--shadow); }}
}}
.kpi.pulse {{ animation: kpiPulse 2s cubic-bezier(.22,.61,.36,1) both; }}
@media (prefers-reduced-motion: reduce) {{ .kpi.pulse {{ animation: none; }} }}

/* ===== clickable channel cards ===== */
[class*="st-key-card_"] {{ position: relative; height: 100%; }}
[class*="st-key-card_"] [data-testid="stElementContainer"]:has([data-testid="stButton"]) {{
  position: absolute !important; inset: 0; width: 100% !important; height: 100%; z-index: 3; margin: 0 !important; }}
[class*="st-key-card_"] [data-testid="stButton"], [class*="st-key-card_"] [data-testid="stButton"] button {{
  width: 100% !important; height: 100% !important; }}
[class*="st-key-card_"] [data-testid="stButton"] button {{ opacity: 0 !important; cursor: pointer; }}
.ch {{ background: var(--surface); border:1px solid var(--border); border-radius: 14px; padding: 14px; min-width:0;
  transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease; height: 100%; }}
[class*="st-key-card_"]:hover .ch {{ border-color: var(--accent); transform: translateY(-2px); box-shadow: 0 8px 20px rgba(16,24,40,.08); }}
[class*="st-key-card_"]:has(button:focus-visible) .ch {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.ch-top {{ display:flex; align-items:center; gap:10px; }}
.ch-top img {{ width:34px; height:34px; border-radius:9px; border:1px solid var(--border); object-fit:cover; background:#fff; }}
.ch-top .n {{ font-weight: 700; font-size: 14px; color: var(--text); }}
.ch-top .s {{ font-size: 12px; color: var(--muted); }}
.ch .v {{ font-size: clamp(17px, 1.35vw, 21px); font-weight: 800; margin-top: 10px; font-variant-numeric: tabular-nums; color: var(--text); }}
.ch .bar {{ height: 6px; background: #EEF0F3; border-radius: 99px; margin: 8px 0 8px; overflow:hidden; }}
.ch .bar > div {{ height: 100%; border-radius: 99px; }}
.ch .meta {{ display:flex; justify-content:space-between; align-items:center; font-size: 12px; color: var(--muted); gap:6px; flex-wrap:wrap; }}
.ch .go {{ margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--border); font-size: 12px; font-weight: 650; color: var(--accent-strong); }}

/* ===== full-width HTML tables (scroll inside their own card, never the page) ===== */
.dt-wrap {{ width: 100%; max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; overscroll-behavior-x: contain;
  background: var(--surface); border: 1px solid var(--border); border-radius: 12px; }}
.dt-wrap.scroll {{ max-height: 480px; overflow-y: auto; }}
table.dt {{ width: 100%; border-collapse: collapse; font-size: clamp(11.5px, 0.82vw, 13.5px); font-variant-numeric: tabular-nums; }}
table.dt th {{ position: sticky; top: 0; background: var(--accent-soft); color: var(--accent-strong); font-weight: 700;
  font-size: .86em; letter-spacing: .02em; text-align: right; padding: 9px 9px; line-height: 1.25;
  border-bottom: 1px solid var(--border); vertical-align: bottom; white-space: normal; }}
table.dt td .vs {{ font-size: .82em; color: var(--muted); font-weight: 500; margin-top: 1px; }}
table.dt td {{ padding: 8px 9px; text-align: right; border-bottom: 1px solid #F0F1F3; white-space: nowrap; color: var(--text); }}
table.dt th:first-child, table.dt td:first-child {{ text-align: left; white-space: nowrap; min-width: 90px; }}
table.dt tbody tr:hover td {{ background: rgba(0,0,0,.018); }}
table.dt td.good {{ color: var(--pos); background: var(--pos-soft); font-weight: 650; }}
table.dt td.bad  {{ color: var(--neg); background: var(--neg-soft); font-weight: 650; }}
table.dt tr.total td {{ font-weight: 750; border-top: 2px solid var(--border); border-bottom: none; background: #FAFAFB; }}
table.dt tr.total td.good {{ background: var(--pos-soft); }} table.dt tr.total td.bad {{ background: var(--neg-soft); }}

/* ===== misc ===== */
[data-testid="stExpander"] details {{ background: var(--surface); border:1px solid var(--border); border-radius: 12px; }}
[data-testid="stDataFrame"] {{ border:1px solid var(--border); border-radius: 12px; overflow:hidden; max-width: 100%; }}
div[data-testid="stPlotlyChart"] {{ background: var(--surface); border:1px solid var(--border); border-radius: 14px; padding: 6px 6px 0; }}
.empty {{ background: var(--surface); border:1px dashed var(--border); border-radius: 14px; padding: 28px; text-align:center; color: var(--muted); }}
/* zero-height helper iframes (scroll-to-top, KPI animation) take no space */
[data-testid="stElementContainer"]:has(iframe[height="0"]) {{ position: absolute !important; width: 0 !important; height: 0 !important; overflow: hidden; }}

/* ===== touch devices: bigger tap targets ===== */
@media (pointer: coarse) {{
  [class*="st-key-pill_"] [data-testid="stRadioOption"] {{ min-height: 44px; padding: 9px 16px; }}
  [data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button {{ min-height: 44px; padding: 10px 16px !important; }}
  .st-key-nav [data-testid="stRadioOption"] {{ height: 50px; }}
}}

/* ===== tablets & phones ===== */
@media (max-width: 768px) {{
  .block-container {{ padding: 3.9rem .75rem 2.5rem !important; }}
  .st-key-hdr {{ padding: 14px 14px 14px; border-radius: 14px; }}
  .hero-logo {{ width: 46px; height: 46px; border-radius: 11px; }}
  .hero-title h1 {{ font-size: 19px; }}
  .hero-title .sub {{ font-size: 12.5px; }}
  /* dates side by side, presets full width underneath */
  .st-key-hdr_row [data-testid="stColumn"]:nth-child(1), .st-key-hdr_row [data-testid="stColumn"]:nth-child(2) {{
    flex: 1 1 calc(50% - 6px) !important; width: calc(50% - 6px) !important; min-width: calc(50% - 6px) !important; }}
  .st-key-hdr_row [data-testid="stColumn"]:nth-child(3) {{ flex: 1 1 100% !important; width: 100% !important; min-width: 100% !important; }}
  [class*="st-key-pill_"] [data-testid="stRadioOption"] p {{ font-size: 13px; }}

  /* tabs wrap into a tidy 3-column grid: no sideways scrolling */
  .st-key-nav [data-testid="stRadioGroup"] {{ display: grid !important; grid-template-columns: repeat(3, minmax(0,1fr));
    gap: 6px !important; border-bottom: none; }}
  .st-key-nav [data-testid="stRadioGroup"] > div {{ min-width: 0; }}
  .st-key-nav [data-testid="stRadioOption"] {{ width: 100%; height: 46px; padding: 0 8px; gap: 6px; margin: 0;
    border-radius: 12px; border-bottom: 1px solid var(--border); justify-content: center; }}
  .st-key-nav [data-testid="stRadioOption"][data-selected="true"] {{ border: 2px solid var(--accent); }}
  .st-key-nav [data-testid="stRadioOption"] p {{ font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; }}
  .st-key-nav [data-testid="stRadioOption"]::before {{ width: 22px; height: 22px; }}

  .sec-head .t {{ font-size: 17px; }}
  .block-title {{ font-size: 14px; margin-top: 16px; }}
  .kpi-grid {{ grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; }}
  .kpi {{ padding: 12px 12px 10px; }}
  .kpi .label {{ font-size: 10.5px; min-height: 0; }}
  .kpi .value {{ font-size: 20px; }}
  .ch {{ padding: 12px; }}
  .ch .v {{ font-size: 19px; }}
  table.dt {{ font-size: 12px; min-width: 620px; }}
  table.dt th, table.dt td {{ padding: 8px 8px; }}
  table.dt th:first-child, table.dt td:first-child {{ position: sticky; left: 0; z-index: 1; background: var(--surface);
    box-shadow: 1px 0 0 var(--border); min-width: 104px; max-width: 140px; white-space: normal; }}
  table.dt th:first-child {{ background: var(--accent-soft); z-index: 2; }}
  table.dt tr.total td:first-child {{ background: #FAFAFB; }}
  div[data-testid="stPlotlyChart"] {{ padding: 2px; }}
}}
@media (max-width: 420px) {{
  .kpi-grid {{ grid-template-columns: 1fr; }}
  .kpi .label {{ min-height: 0; }}
  .kpi .value {{ font-size: 22px; }}
}}
</style>
""",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Small client-side behaviours (zero-height components; see CSS above)
# --------------------------------------------------------------------------- #
def enable_kpi_pulse() -> None:
    """Hover / tap on a KPI card plays a 2-second lift animation, then settles back.
    One delegated listener on the page; survives Streamlit reruns."""
    components.html(
        """<script>
(function () {
  const doc = window.parent.document;
  if (doc.__kpiPulseBound) return;
  doc.__kpiPulseBound = true;
  const fire = (e) => {
    const card = e.target && e.target.closest ? e.target.closest('.kpi') : null;
    if (!card || card.classList.contains('pulse')) return;
    if (e.type === 'pointerover' && e.relatedTarget && card.contains(e.relatedTarget)) return;
    card.classList.add('pulse');
    setTimeout(() => card.classList.remove('pulse'), 2000);
  };
  doc.addEventListener('pointerover', fire, {passive: true});
  doc.addEventListener('touchstart', fire, {passive: true});
})();
</script>""",
        height=0,
    )


def scroll_to_top(nonce: str) -> None:
    """Smoothly scroll the app back to the very top (used after a channel card is clicked)."""
    components.html(
        f"""<script>
/* {nonce} */
(function () {{
  const doc = window.parent.document;
  const go = () => {{
    [doc.querySelector('[data-testid="stMain"]'), doc.querySelector('[data-testid="stMainBlockContainer"]'),
     doc.querySelector('[data-testid="stAppViewContainer"]'), doc.scrollingElement].forEach(el => el && el.scrollTo({{top: 0, behavior: 'smooth'}}));
    try {{ window.parent.scrollTo({{top: 0, behavior: 'smooth'}}); }} catch (e) {{}}
  }};
  go(); setTimeout(go, 150); setTimeout(go, 600);
}})();
</script>""",
        height=0,
    )


# --------------------------------------------------------------------------- #
# Blocks
# --------------------------------------------------------------------------- #
def hero_title(brand: str, theme: dict, period_label: str, compare_label: str | None,
               notes: list[str] | None = None) -> None:
    """Brand logo + title + period line (inside the header card). No refresh pill, no partner icons."""
    title = "All Brands" if brand == "All brands" else brand
    cmp_html = f" &nbsp;·&nbsp; vs <b>{html.escape(compare_label)}</b>" if compare_label else ""
    if brand == "All brands":
        logos = (f'<img class="hero-logo" src="{logo_uri("ChinaTown")}"/>'
                 f'<img class="hero-logo" src="{logo_uri("Nani")}" style="margin-left:-12px"/>')
    else:
        logos = f'<img class="hero-logo" src="{brand_icon(brand, theme)}"/>'
    notes_html = "".join(f'<span class="pill">{html.escape(n)}</span>' for n in (notes or []))
    notes_block = f'<div class="notes">{notes_html}</div>' if notes_html else ""
    # Built without blank lines / deep indentation: Markdown would otherwise turn parts into a code block.
    st.markdown(
        '<div class="hero-left hero-title">'
        f'<div style="display:flex">{logos}</div>'
        f'<div><h1>{html.escape(title)} · Sales Performance</h1>'
        f'<div class="sub"><b>{html.escape(period_label)}</b>{cmp_html}</div>{notes_block}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def sidebar_title(n: int, text: str) -> None:
    st.markdown(f'<div class="sb-h"><span class="n">{n}</span>{html.escape(text)}</div>', unsafe_allow_html=True)


def section_header(icon_uri: str, title: str, desc: str) -> None:
    img = f'<img src="{icon_uri}"/>' if icon_uri else ""
    st.markdown(
        f'<div class="sec-head">{img}<div><div class="t">{html.escape(title)}</div>'
        f'<div class="d">{html.escape(desc)}</div></div></div>',
        unsafe_allow_html=True,
    )


def block_title(text: str, note: str | None = None) -> None:
    st.markdown(f'<div class="block-title">{html.escape(text)}</div>'
                + (f'<div class="block-note">{html.escape(note)}</div>' if note else ""),
                unsafe_allow_html=True)


def kpi_cards(cur: dict, prev: dict | None, compare_label: str | None) -> None:
    """Six KPI cards: value, 'Prior: …' underneath in grey, delta pill on the right.

    Revenue / orders (sales, checks, AOV): up = green, down = red.
    Costs (COGS, COGS %): up = red ('cost rise'), down = green ('cost saving').
    """
    cards = []
    for k in KPIS:
        v = cur.get(k.key)
        is_cost = k.key in COST_KPIS
        label = "COGS (֏)" if k.key == "cogs" else k.label
        pill, prior = "", ""
        if prev is not None:
            pv = prev.get(k.key)
            d, rel = delta(v, pv, k.kind)
            cls = _delta_class(d, k.kind, k.higher_is_better)
            arrow = "▲ " if d and d > 0 else ("▼ " if d and d < 0 else "")
            pill = f'<span class="delta {cls}">{arrow}{fmt_delta(d, rel, k.kind)}</span>'
            tag = ""
            if is_cost and cls != "flat":
                tag = f' · <span class="costtag {cls}">{"cost rise" if d > 0 else "cost saving"}</span>'
            prior = (f'<div class="prior" title="{html.escape(compare_label or "")}">'
                     f'Prior: {fmt_value(pv, k.kind)}{tag}</div>')
        cards.append(
            f'<div class="kpi{" cost" if is_cost else ""}" title="{html.escape(fmt_value(v, k.kind, compact=False))}">'
            f'<div class="label">{label}</div>'
            f'<div class="kpi-row"><div class="value">{fmt_value(v, k.kind)}</div>{pill}</div>'
            f'{prior}</div>'
        )
    st.markdown(f'<div class="kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def channel_card_html(ch: str, cur_bd: pd.DataFrame, prev_bd: pd.DataFrame | None,
                      brand: str, theme: dict) -> str:
    """One channel summary card. App.py overlays an invisible button on it to make it clickable."""
    colors = channel_colors(theme)
    cur_i = cur_bd.set_index("channel") if not cur_bd.empty else pd.DataFrame()
    row = cur_i.loc[ch] if ch in cur_i.index else None
    net = float(row["sales_net"]) if row is not None else 0.0
    gross = float(row["sales_gross"]) if row is not None else 0.0
    checks = float(row["checks"]) if row is not None else 0.0
    total_net = float(cur_bd["sales_net"].sum()) if not cur_bd.empty else 0.0
    total_gross = float(cur_bd["sales_gross"].sum()) if not cur_bd.empty else 0.0

    if ch == "Compliments":
        main, share, sub, key, cur_v = fmt_money(gross), (gross / total_gross if total_gross else 0), \
            "value given (menu price)", "sales_gross", gross
    else:
        main, share, sub, key, cur_v = fmt_money(net), (net / total_net if total_net else 0), \
            "sales after discount", "sales_net", net

    badge = ""
    if prev_bd is not None and not prev_bd.empty:
        prev_i = prev_bd.set_index("channel")
        pv = float(prev_i.loc[ch, key]) if ch in prev_i.index else 0.0
        d, rel = delta(cur_v, pv, "money")
        badge = f'<span class="delta {_delta_class(d, "money", True)}">{fmt_delta(d, rel, "money")}</span>'

    return (
        f'<div class="ch"><div class="ch-top"><img src="{channel_icon(ch, brand, theme)}"/>'
        f'<div><div class="n">{ch}</div><div class="s">{sub}</div></div></div>'
        f'<div class="v">{main}</div>'
        f'<div class="bar"><div style="width:{min(share, 1) * 100:.1f}%;background:{colors[ch]}"></div></div>'
        f'<div class="meta"><span>{share * 100:.1f}% share · {checks:,.0f} checks</span>{badge}</div>'
        f'<div class="go">View {ch} details →</div></div>'
    )


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
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Inter", bordercolor=theme["accent"]),
    )
    fig.update_xaxes(showgrid=False, linecolor=theme["border"], tickfont=dict(color=theme["muted"]))
    fig.update_yaxes(gridcolor="#EEF0F3", zeroline=False, tickfont=dict(color=theme["muted"]))
    return fig


def donut(bd: pd.DataFrame, measure: str, measure_label: str, theme: dict) -> None:
    """Channel share donut. Channels with zero value stay in the legend (e.g. compliments on net sales)."""
    colors = channel_colors(theme)
    d = bd.set_index("channel").reindex(config.CHANNELS).fillna(0.0).reset_index()
    total = d[measure].sum()
    if total <= 0:
        empty_state("No sales in this period.")
        return
    center = fmt_value(total, "count" if measure == "checks" else "money")
    pct = d[measure] / total
    fig = go.Figure(go.Pie(
        labels=d["channel"], values=d[measure], hole=0.64, sort=False,
        marker=dict(colors=[colors.get(c, "#999") for c in d["channel"]], line=dict(color="white", width=2)),
        text=[f"{p * 100:.1f}%" if p >= 0.015 else "" for p in pct], textinfo="text",
        textposition="outside", textfont=dict(size=13, color=theme["text"]),
        customdata=[fmt_value(v, "count" if measure == "checks" else "money", compact=False) for v in d[measure]],
        hovertemplate="<b>%{label}</b><br>%{customdata}<br>%{percent} share<extra></extra>",
        direction="clockwise", rotation=90, showlegend=True,
    ))
    fig.add_annotation(text=f"<b style='font-size:20px'>{center}</b><br><span style='font-size:12px;color:{theme['muted']}'>"
                            f"{measure_label}</span>", showarrow=False, x=0.5, y=0.5)
    _layout(fig, theme, 390)
    fig.update_layout(legend=dict(orientation="h", y=-0.06, x=0.5, xanchor="center", yanchor="top",
                                  traceorder="normal"),
                      margin=dict(l=40, r=40, t=30, b=30))
    st.plotly_chart(fig, width="stretch", config=PLOT_CFG)


def trend(cur: pd.DataFrame, prev_tot: pd.DataFrame | None, by: str, order: list[str], colors: dict,
          theme: dict, level: str, value: str, prev_label: str | None) -> None:
    """Stacked bars per bucket (by channel or payment type) + dotted comparison line.

    `cur` comes from data.aggregate(..., by=[by]); `prev_tot` from data.aggregate(...) with its
    bucket_idx already aligned to the current buckets (period N vs comparison period N).
    """
    if cur.empty or cur[value].sum() == 0:
        empty_state("No sales in this period.")
        return
    fig = go.Figure()
    hover_x = {"Daily": "%{customdata}", "Weekly": "%{customdata}", "Monthly": "%{customdata}"}[level]
    for name in order:
        part = cur[cur[by] == name]
        if part.empty or part[value].sum() == 0:
            continue
        fig.add_bar(x=part["period_start"], y=part[value], name=name, marker_color=colors.get(name),
                    customdata=part["period"],
                    hovertemplate=f"<b>{name}</b><br>{hover_x}<br>%{{y:,.0f}} {CURRENCY}<extra></extra>")
    if prev_tot is not None and not prev_tot.empty:
        fig.add_scatter(x=prev_tot["x"], y=prev_tot[value], name=f"Comparison ({prev_label})",
                        mode="lines+markers", customdata=prev_tot["period"],
                        line=dict(color=theme["accent_strong"], width=2, dash="dot"), marker=dict(size=6),
                        hovertemplate=f"<b>Comparison</b><br>%{{customdata}}<br>%{{y:,.0f}} {CURRENCY}<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.22)
    fig.update_xaxes(tickformat={"Daily": "%d %b", "Weekly": "%d %b", "Monthly": "%b %Y"}[level],
                     dtick="M1" if level == "Monthly" else None)
    fig.update_yaxes(tickformat="~s")
    st.plotly_chart(_layout(fig, theme, 360), width="stretch", config=PLOT_CFG)


def payment_bars(cur_bd: pd.DataFrame, prev_bd: pd.DataFrame | None, theme: dict, measure="sales_net") -> None:
    if cur_bd.empty:
        empty_state("No sales in this period.")
        return
    d = cur_bd.sort_values(measure)
    fig = go.Figure()
    pmax = 0.0
    if prev_bd is not None and not prev_bd.empty:
        p = prev_bd.set_index("payment_label")[measure].reindex(d["payment_label"]).fillna(0)
        pmax = float(p.max())
        fig.add_bar(y=d["payment_label"], x=p.values, orientation="h", name="Comparison",
                    marker_color="#CBD2DA", hovertemplate=f"%{{x:,.0f}} {CURRENCY}<extra>Comparison</extra>")
    fig.add_bar(y=d["payment_label"], x=d[measure], orientation="h", name="Current",
                marker_color=theme["accent"], text=[fmt_money(v) for v in d[measure]], textposition="outside",
                cliponaxis=False, hovertemplate=f"%{{x:,.0f}} {CURRENCY}<extra>Current</extra>")
    fig.update_layout(barmode="group", bargap=0.3)
    xmax = max(float(d[measure].max()), pmax)
    fig.update_xaxes(tickformat="~s", gridcolor="#EEF0F3", showgrid=True, range=[0, (xmax * 1.28) or 1])
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(_layout(fig, theme, max(240, 60 + 46 * len(d))), width="stretch", config=PLOT_CFG)


# --------------------------------------------------------------------------- #
# Tables (pure HTML → always 100 % container width, no clipping, wraps headers)
# --------------------------------------------------------------------------- #
SUMS = ["sales_gross", "sales_net", "checks", "cogs"]


def _ratios(s: pd.DataFrame) -> pd.DataFrame:
    s = s.copy()
    s["aov"] = (s["sales_net"] / s["checks"]).where(s["checks"] > 0)
    s["cogs_pct"] = (s["cogs"] / s["sales_net"]).where(s["sales_net"] > 0)
    return s


def _rel(a, b):
    return (a - b) / b.where(b != 0)


def variance_table(cur: pd.DataFrame, prev: pd.DataFrame | None, key_label: str,
                   compared_with: list[str] | None = None, scroll: bool = False) -> str:
    """HTML table: one row per index value of `cur` (+ Total), KPI columns and, when `prev`
    is given (same index, aligned), variance columns coloured green/red.

    Cost columns (Δ COGS, Δ COGS share) are inverted: an increase is a cost rise → red.
    """
    if cur.empty:
        return ""
    cur = cur[SUMS].astype(float)
    tot = cur.sum().to_frame().T
    tot.index = ["Total"]
    c = _ratios(pd.concat([cur, tot]))

    cols = [  # (header, values, kind)
        ("Sales before disc.", c["sales_gross"], "money"),
        ("Sales after disc.", c["sales_net"], "money"),
        ("Checks", c["checks"], "count"),
        ("AOV", c["aov"], "money"),
        ("COGS (֏)", c["cogs"], "money"),
        ("COGS %", c["cogs_pct"], "pct"),
    ]
    good_bad: dict[str, tuple[pd.Series, bool]] = {}
    if prev is not None:
        p = prev.reindex(cur.index)[SUMS].astype(float)
        ptot = prev[SUMS].astype(float).sum().to_frame().T
        ptot.index = ["Total"]
        p = _ratios(pd.concat([p, ptot]))
        dSp = _rel(c["sales_net"], p["sales_net"])
        dC, dA = _rel(c["checks"], p["checks"]), _rel(c["aov"], p["aov"])
        dG, dGp = _rel(c["cogs"], p["cogs"]), (c["cogs_pct"] - p["cogs_pct"]) * 100
        cols += [
            ("Δ Sales %", dSp, "spct"), ("Δ Checks %", dC, "spct"), ("Δ AOV %", dA, "spct"),
            ("Δ COGS % (cost)", dG, "spct"), ("Δ COGS share (pp)", dGp, "spp"),
        ]
        # revenue/orders: up = green · costs: up = red (cost rise), down = green (saving)
        good_bad = {"Δ Sales %": (dSp, True), "Δ Checks %": (dC, True), "Δ AOV %": (dA, True),
                    "Δ COGS % (cost)": (dG, False), "Δ COGS share (pp)": (dGp, False)}

    def fmt(v, kind):
        if kind == "text":
            return html.escape(str(v))
        if v is None or pd.isna(v):
            return "—"
        return {"money": f"{v:,.0f}", "count": f"{v:,.0f}", "pct": f"{v * 100:.1f}%",
                "smoney": f"{v:+,.0f}", "spct": f"{v * 100:+.1f}%", "spp": f"{v:+.1f} pp"}[kind]

    head = f"<th>{html.escape(key_label)}</th>" + "".join(f"<th>{html.escape(h)}</th>" for h, _, _ in cols)
    rows = []
    for i, idx in enumerate(c.index):
        is_total = i == len(c.index) - 1
        vs = ""
        if compared_with is not None and not is_total and i < len(compared_with):
            vs = f'<div class="vs">vs {html.escape(compared_with[i])}</div>'
        tds = [f"<td>{html.escape(str(idx))}{vs}</td>"]
        for h, series, kind in cols:
            v = series.iloc[i]
            cls = ""
            if h in good_bad and not (v is None or pd.isna(v)) and abs(v) > 1e-9:
                cls = "good" if (v > 0) == good_bad[h][1] else "bad"
            if kind == "text":
                cls = "txt"
            tds.append(f'<td class="{cls}">{fmt(v, kind)}</td>')
        rows.append(f'<tr class="{"total" if is_total else ""}">{"".join(tds)}</tr>')
    return f'<div class="dt-wrap{" scroll" if scroll else ""}"><table class="dt"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def show_html(markup: str) -> None:
    if markup:
        st.markdown(markup, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Raw / detailed records (st.dataframe: sortable, searchable, downloadable)
# --------------------------------------------------------------------------- #
def records_table(cur_agg: pd.DataFrame, prev_agg: pd.DataFrame | None) -> pd.DataFrame:
    """Rows = period (day / week / month) × brand × channel × payment type.
    With a comparison, the same row in the aligned comparison period is matched and Δ % added."""
    keys = ["bucket_idx", "brand", "channel", "payment_label"]
    out = cur_agg.copy()
    if prev_agg is not None:
        p = prev_agg[keys + ["sales_net", "period"]].rename(
            columns={"sales_net": "prev_sales_net", "period": "prev_period"})
        out = out.merge(p, on=keys, how="left")
        out["delta_pct"] = ((out["sales_net"] - out["prev_sales_net"]) /
                            out["prev_sales_net"].where(out["prev_sales_net"] != 0)) * 100
    out = out.sort_values(["period_start", "brand", "channel", "sales_net"], ascending=[False, True, True, False])
    table = pd.DataFrame({
        "Period": out["period"],
        "Brand": out["brand"],
        "Channel": out["channel"],
        "Payment type": out["payment_label"],
        "Sales before disc.": out["sales_gross"].round(0),
        "Sales after disc.": out["sales_net"].round(0),
        "Checks": out["checks"].round(1),
        "AOV": out["aov"].round(0),
        "COGS": out["cogs"].round(0),
        "COGS %": (out["cogs_pct"] * 100).round(1),
    })
    if prev_agg is not None:
        table["Prev sales after disc."] = out["prev_sales_net"].round(0)
        table["Δ Sales %"] = out["delta_pct"].round(1)
    return table.reset_index(drop=True)


def _pct_text(v, signed=False) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v:+.1f}%" if signed else f"{v:.1f}%"


def style_records(table: pd.DataFrame):
    """Numbers stay numeric (sortable, formatted by RECORDS_COLUMN_CONFIG); the two percentage
    columns become text so empty values read '—'. Δ Sales % is highlighted green/red."""
    t = table.copy()
    t["COGS %"] = t["COGS %"].map(_pct_text)
    if "Δ Sales %" in t:
        t["Δ Sales %"] = t["Δ Sales %"].map(lambda v: _pct_text(v, signed=True))

        def color(v: str):
            if not v or v == "—" or v in ("+0.0%", "-0.0%"):
                return ""
            ok = v.startswith("+")
            return (f"color:{config.POSITIVE if ok else config.NEGATIVE};"
                    f"background-color:{config.POSITIVE_SOFT if ok else config.NEGATIVE_SOFT};font-weight:600")
        return t.style.map(color, subset=["Δ Sales %"])
    return t.style


RECORDS_COLUMN_CONFIG = {
    "Sales before disc.": st.column_config.NumberColumn(format="localized"),
    "Sales after disc.": st.column_config.NumberColumn(format="localized"),
    "Checks": st.column_config.NumberColumn(format="localized"),
    "AOV": st.column_config.NumberColumn(format="localized"),
    "COGS": st.column_config.NumberColumn(format="localized"),
    "Prev sales after disc.": st.column_config.NumberColumn(format="localized"),
}

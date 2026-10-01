"""Central configuration: data sources, column mapping, channel rules, brand themes."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
LOCAL_DATA = ROOT / "data"          # optional local copies for offline/dev use
TIMEZONE = "Asia/Yerevan"
CACHE_TTL_SECONDS = 600             # re-download Dropbox files at most every 10 min

# --------------------------------------------------------------------------- #
# Data sources (override in .streamlit/secrets.toml with HISTORY_URL / UPDATE_URL)
# --------------------------------------------------------------------------- #
DEFAULT_SOURCES = {
    "HISTORY_URL": "https://www.dropbox.com/scl/fi/de8f4z9gr4buoqxvr5zj0/Sales-History.xlsx"
                   "?rlkey=9j5j2178oow9av3r6hih4g5r5&dl=0",
    "UPDATE_URL": "https://www.dropbox.com/scl/fi/klbpxud1nln96sey222pq/Update-Sales.xlsx"
                  "?rlkey=bira1cz2bbzv2x20zzijvycqr&dl=0",
}
LOCAL_FALLBACK = {"HISTORY_URL": "Sales History.xlsx", "UPDATE_URL": "Update Sales.xlsx"}

# --------------------------------------------------------------------------- #
# iiko OLAP column mapping -> internal names. Matching is by keyword so small
# header differences ("со скидкой" vs "со скидки") don't break the parser.
# Order matters: first matching rule wins.
# --------------------------------------------------------------------------- #
COLUMN_RULES = [
    ("group",          ["группа"]),
    ("date",           ["учетный день"]),
    ("payment_type",   ["тип оплаты"]),
    ("sales_gross",    ["без скидки"]),
    ("sales_net",      ["со скидк"]),
    ("checks",         ["заказов"]),
    ("aov",            ["средняя сумма"]),
    ("cogs_pct",       ["себестоимость(%)", "себестоимость (%)"]),
    ("cogs",           ["себестоимость"]),
]

# Raw group names in iiko -> dashboard brand
GROUP_RULES = [
    ("ChinaTown", ["china"]),
    ("Nani",      ["նանի", "nani", "нани"]),
]

# Payment type -> sales channel. Checked in order; anything unmatched is "Hall".
CHANNEL_RULES = [
    ("Compliments", ["без оплаты"]),
    ("Yandex",      ["yandex", "яндекс"]),     # includes "Yandex staff"
    ("Glovo",       ["glovo"]),
    ("Buy.am",      ["buy.am", "buyam", "buy am"]),
]
CHANNELS = ["Hall", "Yandex", "Glovo", "Buy.am", "Compliments"]

# Friendly English names for iiko payment types (unknown ones are shown as-is)
PAYMENT_LABELS = {
    "Банковские карты": "Bank cards",
    "Наличные": "Cash",
    "(без оплаты)": "No payment (compliment)",
    "Փոխանցումով": "Bank transfer",
    "Gift card": "Gift card",
    "Idram": "Idram",
    "TelCell": "TelCell",
}

BRANDS = ["ChinaTown", "Nani", "All brands"]

LOGOS = {
    "ChinaTown": "chinatown.png",
    "Nani": "nani.png",
    "Yandex": "yandex.png",
    "Yandex_icon": "yandex_icon.png",
    "Glovo": "glovo.png",
    "Buy.am": "buyam.png",
}

# --------------------------------------------------------------------------- #
# Brand themes
# --------------------------------------------------------------------------- #
THEMES = {
    "ChinaTown": {
        "accent": "#D9383A", "accent_strong": "#A8262A", "accent_soft": "#FBE3E1",
        "bg": "#FFF8F6", "surface": "#FFFFFF", "border": "#F1D5D1",
        "text": "#2A1B1A", "muted": "#7B6461", "hero_from": "#FFFFFF", "hero_to": "#FDE7E4",
        "hall": "#D9383A",
    },
    "Nani": {
        "accent": "#E6A100", "accent_strong": "#8F5B00", "accent_soft": "#FFF1CC",
        "bg": "#FFFCF4", "surface": "#FFFFFF", "border": "#EFE0B8",
        "text": "#2A2112", "muted": "#7A6A4A", "hero_from": "#FFFFFF", "hero_to": "#FFF0C7",
        "hall": "#B37400",
    },
    "All brands": {
        "accent": "#334155", "accent_strong": "#1E293B", "accent_soft": "#E8EDF3",
        "bg": "#F7F8FA", "surface": "#FFFFFF", "border": "#E2E6EC",
        "text": "#141A23", "muted": "#5F6B7A", "hero_from": "#FFFFFF", "hero_to": "#EEF1F5",
        "hall": "#334155",
    },
}

# Partner colours (Hall colour comes from the active brand theme)
CHANNEL_COLORS = {
    "Yandex": "#F7C600",
    "Glovo": "#00A082",
    "Buy.am": "#E0156E",
    "Compliments": "#9AA3AE",
}

POSITIVE = "#15803D"
NEGATIVE = "#C0262D"
POSITIVE_SOFT = "#E6F4EA"
NEGATIVE_SOFT = "#FCE8E8"

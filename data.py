"""Download and clean the iiko OLAP exports (Sales History + Update Sales).

The iiko OLAP Excel export is a *pivot-style* sheet:
  - 3-4 title rows ("AI update", "Название ресторана…", "Период…", "Итого")
  - a header row containing "Учетный день"
  - Group and Date are only filled on the first row of each block
  - subtotal rows ("02.01.2026 всего", "China Town всего", "Итого")
This module turns that into a tidy one-row-per (brand, day, payment type) table.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pandas as pd
import requests
import streamlit as st

from . import config

NUMERIC = ["sales_gross", "sales_net", "checks", "cogs"]


@dataclass
class LoadResult:
    df: pd.DataFrame
    messages: list[str]


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
def direct_download_url(url: str) -> str:
    """Dropbox share link -> direct file download link (dl=1)."""
    if "dropbox.com" not in url:
        return url
    if re.search(r"[?&]dl=\d", url):
        return re.sub(r"([?&])dl=\d", r"\1dl=1", url)
    return url + ("&" if "?" in url else "?") + "dl=1"


def _secret(key: str) -> str:
    try:
        return st.secrets.get(key, config.DEFAULT_SOURCES[key])
    except Exception:  # no secrets.toml at all
        return config.DEFAULT_SOURCES[key]


@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def _download(url: str) -> bytes:
    resp = requests.get(direct_download_url(url), timeout=60)
    resp.raise_for_status()
    if resp.content[:2] != b"PK":  # xlsx files are zip archives
        raise ValueError("Link did not return an .xlsx file (is the Dropbox link still shared?)")
    return resp.content


def _read_source(key: str, messages: list[str]) -> pd.DataFrame | None:
    url = _secret(key)
    try:
        return parse_iiko_excel(_download(url))
    except Exception as exc:  # fall back to a local copy in /data if present
        local = config.LOCAL_DATA / config.LOCAL_FALLBACK[key]
        if local.exists():
            messages.append(f"Dropbox download failed for {local.name} ({type(exc).__name__}) — showing the local copy in /data.")
            return parse_iiko_excel(local.read_bytes())
        messages.append(f"Could not load {config.LOCAL_FALLBACK[key]}: {exc}")
        return None


# --------------------------------------------------------------------------- #
# Parse
# --------------------------------------------------------------------------- #
def _match(text: str, rules) -> str | None:
    low = str(text).strip().lower()
    for name, keys in rules:
        if any(k in low for k in keys):
            return name
    return None


def parse_iiko_excel(content: bytes) -> pd.DataFrame:
    raw = pd.read_excel(io.BytesIO(content), header=None, sheet_name=0)

    # 1. locate the header row
    header_idx = next(
        (i for i in range(min(25, len(raw)))
         if raw.iloc[i].astype(str).str.contains("Учетный день", case=False).any()),
        None,
    )
    if header_idx is None:
        raise ValueError("Header row with 'Учетный день' not found")

    headers = raw.iloc[header_idx].tolist()
    body = raw.iloc[header_idx + 1:].reset_index(drop=True)

    # 2. map columns by keyword
    cols: dict[str, int] = {}
    for pos, h in enumerate(headers):
        if pd.isna(h):
            continue
        name = _match(h, config.COLUMN_RULES)
        if name and name not in cols:
            cols[name] = pos
    missing = {"group", "date", "payment_type", "sales_gross", "sales_net", "checks", "cogs"} - cols.keys()
    if missing:
        raise ValueError(f"Missing columns in export: {sorted(missing)}")

    df = pd.DataFrame({name: body.iloc[:, pos] for name, pos in cols.items()})

    # 3. groups: drop subtotal labels, then forward-fill
    grp = df["group"].astype("string")
    grp = grp.where(~grp.str.contains("всего|итого", case=False, na=False))
    df["group"] = grp.ffill()

    # 4. dates: subtotal strings ("02.01.2026 всего") become NaT, then forward-fill
    def to_date(v):
        if isinstance(v, (pd.Timestamp,)) or hasattr(v, "year"):
            return pd.Timestamp(v)
        if isinstance(v, str) and "всего" not in v.lower():
            return pd.to_datetime(v.strip(), dayfirst=True, errors="coerce")
        return pd.NaT

    is_subtotal = df["date"].astype(str).str.contains("всего", case=False, na=False)
    df["date"] = df["date"].map(to_date)
    df.loc[is_subtotal, "date"] = pd.NaT
    df["date"] = df["date"].ffill()

    # 5. keep only detail rows (payment type present, not subtotal)
    df = df[df["payment_type"].notna() & ~is_subtotal].copy()
    df["payment_type"] = df["payment_type"].astype(str).str.strip()

    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    df["brand"] = df["group"].map(lambda g: _match(g, config.GROUP_RULES) or str(g).strip())
    df["channel"] = df["payment_type"].map(lambda p: _match(p, config.CHANNEL_RULES) or "Hall")
    df["payment_label"] = df["payment_type"].map(lambda p: config.PAYMENT_LABELS.get(p, p))
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()

    return df[["date", "brand", "channel", "payment_type", "payment_label", *NUMERIC]].dropna(subset=["date"])


# --------------------------------------------------------------------------- #
# Public
# --------------------------------------------------------------------------- #
def load_sales() -> LoadResult:
    messages: list[str] = []
    hist = _read_source("HISTORY_URL", messages)
    upd = _read_source("UPDATE_URL", messages)
    frames = [f for f in (hist, upd) if f is not None and not f.empty]
    if not frames:
        return LoadResult(pd.DataFrame(), messages)

    if hist is not None and upd is not None and not upd.empty:
        # the live file wins for any day present in both
        hist = hist[~hist["date"].isin(set(upd["date"]))]
        frames = [hist, upd]

    df = pd.concat(frames, ignore_index=True).sort_values(["date", "brand", "channel"])
    return LoadResult(df.reset_index(drop=True), messages)


def clear_cache() -> None:
    _download.clear()

from __future__ import annotations
import os
import json
import threading
from pathlib import Path
from typing import List

import pandas as pd
import streamlit as st

from src.util import (
    ensure_dirs,
    csv_path_for,
    html_path_for,        # kept for parity / future use
    file_age_minutes,
    is_stale,
)
from src.fetch_shots import get_or_fetch_shots
from src.plot_shot_chart import plot_plotly


# ---------------------------
# Demo fallback helper
# ---------------------------
DEMO_PNG = Path("outputs/figures/screenshot.png")
DEMO_HTML = Path("outputs/html/demo.html")  # optional if you have one

def show_demo() -> None:
    """Always show *something* even if cache/network is unavailable."""
    st.info("Using demo preview (network/cache unavailable).")
    if DEMO_HTML.exists():
        st.components.v1.html(DEMO_HTML.read_text(encoding="utf-8"), height=760, scrolling=True)
    elif DEMO_PNG.exists():
        st.image(str(DEMO_PNG), use_container_width=True)
    else:
        st.warning("Demo asset not found. Add outputs/figures/screenshot.png or outputs/html/demo.html.")
    st.caption(
        "Tip: To fetch live data later, run locally with headers in "
        ".streamlit/secrets.toml and disable Demo mode."
    )
    st.stop()

def csv_has_rows(p: str | Path) -> bool:
    """Return True only if CSV exists and has at least one data row."""
    try:
        p = Path(p)
        if not p.exists() or p.stat().st_size == 0:
            return False
        df_preview = pd.read_csv(p, nrows=1)
        return len(df_preview) > 0
    except Exception:
        return False


# ---------------------------
# Page config / styling
# ---------------------------
st.set_page_config(page_title="NBA Shot Chart Visualizer", layout="wide")

ensure_dirs("data/raw", "outputs/html", "outputs/figures")

st.markdown(
    """
    <style>
      .stApp { background-color: #0f1115; }
      .block-container { padding-top: 1.2rem; }
      .chart-wrapper { background: #0f1115; padding: 12px; border-radius: 8px; border: 1px solid #222; }
      .player-title { color: #e6e6e6; font-weight: 700; font-size: 1.1rem; margin: 0 0 8px 0; }
      .status-row { color: #a0a0a0; font-size: 0.9rem; margin-top: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.expander("Help & Notes (click to expand)"):
    st.write(
        """
        - Uses NBA.com Stats via `nba_api`. Requests may be throttled; cloud/shared IPs may be blocked.
        - Provide request headers via Streamlit secrets or environment for better reliability:
          - `.streamlit/secrets.toml`:
            ```
            NBA_API_HEADERS = "{\"User-Agent\":\"Mozilla/5.0\",\"x-nba-stats-origin\":\"stats\",\"Referer\":\"https://stats.nba.com/\"}"
            ```
          - Or set env var `NBA_API_HEADERS` to the same JSON.
        - Demo Mode shows a bundled example chart when cache/network is unavailable.
        """
    )


# ---------------------------
# Load headers from secrets/env (defensive)
# ---------------------------
headers: dict | None = None
try:
    raw = st.secrets.get("NBA_API_HEADERS", None)
    if raw:
        headers = json.loads(raw) if isinstance(raw, str) else raw
except Exception:
    pass

if headers is None and os.getenv("NBA_API_HEADERS"):
    try:
        headers = json.loads(os.environ["NBA_API_HEADERS"])
    except Exception:
        pass


# ---------------------------
# Cached helpers
# ---------------------------
@st.cache_data(show_spinner=False)
def load_cached_csv(csv_path: str) -> str | None:
    """Return the path if it exists (so Streamlit can cache the value), else None."""
    return csv_path if Path(csv_path).exists() else None


# ---------------------------
# Background refresh
# ---------------------------
def refresh_async(player: str, season: str, season_type: str, headers: dict | None) -> None:
    def _target():
        try:
            get_or_fetch_shots(player, season, season_type, headers=headers, force_refresh=True)
            st.session_state[f"refresh_done_{player}"] = True
        except Exception as e:
            st.session_state[f"refresh_err_{player}"] = str(e)
    t = threading.Thread(target=_target, daemon=True)
    t.start()


# ---------------------------
# Sidebar controls
# ---------------------------
st.sidebar.header("Controls")
players_str = st.sidebar.text_input(
    "Player(s)",
    value="Stephen Curry",
    help='Comma-separated, e.g., "Stephen Curry, LeBron James"',
)
season = st.sidebar.selectbox("Season", ["2023-24", "2022-23", "2021-22"])
season_type = st.sidebar.selectbox("Season Type", ["Regular Season", "Playoffs", "Pre Season", "All Star"])
metric = st.sidebar.radio("Metric", ["fg_pct", "frequency"], index=0)

use_cache_only = st.sidebar.checkbox("Use cache only (no live fetch)", value=False)
fresh_minutes = st.sidebar.number_input("Cache freshness (minutes)", min_value=1, max_value=10080, value=1440)

demo_mode = st.sidebar.checkbox(
    "Demo mode (no live data)",
    value=True,
    help="Show a bundled example chart if cache/network is unavailable.",
)

# Force refresh flag per run
if "force_refresh" not in st.session_state:
    st.session_state["force_refresh"] = False
if st.sidebar.button("Force refresh"):
    st.session_state["force_refresh"] = True

go = st.sidebar.button("Generate charts")


# ---------------------------
# Main
# ---------------------------
st.title("NBA Shot Chart Visualizer")
st.caption("Interactive charts powered by NBA.com Stats via nba_api")

if go:
    players: List[str] = [p.strip() for p in players_str.split(",") if p.strip()]
    if not players:
        st.warning("Please enter at least one player name.")
    else:
        for idx, player in enumerate(players, start=1):
            st.markdown(f"<div class='player-title'>{idx}. {player}</div>", unsafe_allow_html=True)
            try:
                csv: str | None = None
                kicked_bg_refresh = False
                data_source = "cache"

                if not demo_mode:
                    # ------------- Cache-first logic -------------
                    csv_path = csv_path_for(player, season, season_type)
                    age_min = file_age_minutes(csv_path)
                    stale = is_stale(csv_path, max_minutes=float(fresh_minutes))

                    if use_cache_only:
                        # Cache only: require an existing CSV with rows
                        if not csv_has_rows(csv_path):
                            st.warning(f"No cache found for {player}. Enable live fetch later or seed the cache.")
                            continue
                        csv = csv_path
                        data_source = "cache"
                    else:
                        # Live allowed (polite):
                        if st.session_state.get("force_refresh", False):
                            # Blocking live fetch
                            res = get_or_fetch_shots(
                                player, season, season_type, headers=headers, force_refresh=True
                            )
                            if res and csv_has_rows(res):
                                csv = res
                                data_source = "Live-refreshed"
                            else:
                                if csv_has_rows(csv_path):
                                    st.warning(
                                        f"NBA Stats API may be throttling for {player}. Using cached data."
                                    )
                                    csv = csv_path
                                else:
                                    show_demo()
                        else:
                            # Not forcing: cache-first
                            if csv_has_rows(csv_path) and not stale:
                                csv = csv_path
                                data_source = "cache"
                            else:
                                # If some cache exists, show it and refresh in background
                                if csv_has_rows(csv_path):
                                    csv = csv_path
                                    kicked_bg_refresh = True
                                    refresh_async(player, season, season_type, headers)
                                else:
                                    # No cache: attempt a blocking fetch once
                                    res = get_or_fetch_shots(
                                        player, season, season_type, headers=headers, force_refresh=True
                                    )
                                    if res and csv_has_rows(res):
                                        csv = res
                                        data_source = "Live-refreshed"
                                    else:
                                        # Nothing → demo fallback
                                        show_demo()
                else:
                    # Demo Mode: skip any network attempts and force fallback if no cache
                    csv = None

                # ------------- Fallback if no CSV or no data -------------
                if csv is None or not csv_has_rows(csv):
                    show_demo()

                # ------------- Plot & embed -------------
                html_path = plot_plotly(csv, player, season, season_type, metric)
                try:
                    html_text = Path(html_path).read_text(encoding="utf-8")
                except Exception as e:
                    st.warning(
                        f"Unable to render chart for {player}. Using any cached data if available. Details: {e}"
                    )
                    continue

                st.markdown("<div class='chart-wrapper'>", unsafe_allow_html=True)
                st.components.v1.html(html_text, height=760, scrolling=True)
                st.markdown("</div>", unsafe_allow_html=True)

                # ------------- Status row -------------
                age_min = file_age_minutes(csv)
                last_updated = f"Last updated: {age_min:.1f} min ago" if age_min is not None else "Last updated: N/A"
                effective_source = "demo" if demo_mode else data_source
                st.markdown(
                    f"<div class='status-row'>Data source: {effective_source} • {last_updated}</div>",
                    unsafe_allow_html=True,
                )

                if not demo_mode and kicked_bg_refresh and not st.session_state.get(f"refresh_done_{player}"):
                    st.markdown("<div class='status-row'>Refreshing in background… ⏳</div>", unsafe_allow_html=True)
                if not demo_mode and st.session_state.get(f"refresh_done_{player}"):
                    st.info("Refreshed. Click 'Generate charts' again to load the latest.")

            except Exception as e:
                st.warning(
                    f"NBA Stats API may be throttling for {player}. "
                    f"Using any cached data if available. Details: {e}"
                )
                continue

        # Reset the force-refresh flag after the whole run
        st.session_state["force_refresh"] = False
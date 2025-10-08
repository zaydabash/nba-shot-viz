from __future__ import annotations
import os, json, threading, time
from pathlib import Path
from typing import List

import streamlit as st

from src.util import ensure_dirs, csv_path_for, html_path_for, file_age_minutes, is_stale
from src.fetch_shots import get_or_fetch_shots
from src.plot_shot_chart import plot_plotly

# Page config
st.set_page_config(page_title="NBA Shot Chart Visualizer", layout="wide")

# Ensure directories
ensure_dirs("data/raw", "outputs/html", "outputs/figures")

# Dark aesthetics CSS
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
        - Uses NBA.com Stats via `nba_api`. Requests may be throttled; cloud IPs may be blocked.
        - Provide custom request headers via Streamlit secrets or env to improve reliability:
          - `.streamlit/secrets.toml`: NBA_API_HEADERS = "{\"User-Agent\":\"Mozilla/5.0\",\"x-nba-stats-origin\":\"stats\",\"Referer\":\"https://stats.nba.com/\"}"
          - Or set env var NBA_API_HEADERS to the same JSON.
        """
    )

# Secrets/env headers (defensive)
headers = None
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

# Cached helpers
@st.cache_data(show_spinner=False)
def load_cached_csv(csv_path: str) -> str | None:
    return csv_path if Path(csv_path).exists() else None

# Background refresh logic
def refresh_async(player: str, season: str, season_type: str, headers: dict | None):
    def _target():
        try:
            get_or_fetch_shots(player, season, season_type, headers=headers, force_refresh=True)
            st.session_state[f"refresh_done_{player}"] = True
        except Exception as e:
            st.session_state[f"refresh_err_{player}"] = str(e)
    t = threading.Thread(target=_target, daemon=True)
    t.start()

# Sidebar controls
st.sidebar.header("Controls")
players_str = st.sidebar.text_input("Player(s)", value="Stephen Curry", help='Comma-separated, e.g., "Stephen Curry, LeBron James"')
season = st.sidebar.selectbox("Season", ["2023-24", "2022-23", "2021-22"])
season_type = st.sidebar.selectbox("Season Type", ["Regular Season", "Playoffs", "Pre Season", "All Star"])
metric = st.sidebar.radio("Metric", ["fg_pct", "frequency"], index=0)
use_cache_only = st.sidebar.checkbox("Use cache only (no live fetch)", value=False)
fresh_minutes = st.sidebar.number_input("Cache freshness (minutes)", min_value=1, max_value=10080, value=1440)
demo_mode = st.sidebar.checkbox("Demo mode (no live data)", value=True,
                                help="Show a bundled example chart if cache/network is unavailable.")

# Force refresh session flag
if "force_refresh" not in st.session_state:
    st.session_state["force_refresh"] = False
if st.sidebar.button("Force refresh"):
    st.session_state["force_refresh"] = True

go = st.sidebar.button("Generate charts")

st.title("🏀 NBA Shot Chart Visualizer")
st.caption("Interactive charts powered by NBA.com Stats via nba_api")

if go:
    players: List[str] = [p.strip() for p in players_str.split(",") if p.strip()]
    if not players:
        st.warning("Please enter at least one player name.")
    else:
        for idx, player in enumerate(players, start=1):
            st.markdown(f"<div class='player-title'>{idx}. {player}</div>", unsafe_allow_html=True)
            try:
                csv = None
                if not demo_mode:
                    # existing cache-first logic
                    csv_path = csv_path_for(player, season, season_type)
                    age_min = file_age_minutes(csv_path)
                    stale = is_stale(csv_path, max_minutes=float(fresh_minutes))

                    data_source = "cache"
                    kicked_bg_refresh = False

                    if use_cache_only:
                        if not Path(csv_path).exists():
                            st.warning(f"No cache found for {player}. Enable live fetch or reduce freshness window.")
                            continue
                    else:
                        if st.session_state.get("force_refresh", False):
                            # blocking live fetch
                            res = get_or_fetch_shots(player, season, season_type, headers=headers, force_refresh=True)
                            if res:
                                csv_path = res
                                data_source = "Live-refreshed"
                            else:
                                st.warning(f"NBA Stats API may be throttling for {player}. Using any cached data if available.")
                        else:
                            if Path(csv_path).exists() and not stale:
                                # use fresh cache
                                pass
                            else:
                                # cache-first UX: show old chart if exists, kick background refresh
                                if Path(csv_path).exists():
                                    kicked_bg_refresh = True
                                    refresh_async(player, season, season_type, headers)
                                else:
                                    # no cache -> do a blocking fetch once
                                    res = get_or_fetch_shots(player, season, season_type, headers=headers, force_refresh=True)
                                    if res:
                                        csv_path = res
                                        data_source = "Live-refreshed"
                                    else:
                                        st.warning(f"NBA Stats API may be throttling for {player}. Using any cached data if available.")
                                        continue

                    # At this point, csv_path should exist (or we continued)
                    if not Path(csv_path).exists() or Path(csv_path).stat().st_size == 0:
                        st.warning(f"No data available for {player}. Try again later or switch networks.")
                        continue
                    
                    csv = csv_path
                else:
                    # DEMO MODE: if we don't have a cached CSV for the player, just skip fetch
                    # and show a bundled example figure/HTML instead.
                    csv = None  # force the fallback below

                # Fallback block for demo mode or missing data
                if csv is None or not Path(csv).exists():
                    # Try to display a local demo asset
                    demo_png = Path("outputs/figures/screenshot.png")
                    demo_html = Path("outputs/html/demo.html")  # optional if you have it
                    st.info("Using demo preview (no cache found or network blocked).")
                    if demo_html.exists():
                        st.components.v1.html(demo_html.read_text(encoding="utf-8"), height=760, scrolling=True)
                    elif demo_png.exists():
                        st.image(str(demo_png), use_column_width=True)
                    else:
                        st.warning("Demo asset not found. Add outputs/figures/screenshot.png or outputs/html/demo.html.")
                    # Show a tiny note explaining how to enable real fetch:
                    st.caption("Tip: Turn off 'Demo mode' and run locally with headers in .streamlit/secrets.toml to fetch live data.")
                    st.stop()

                # Normal flow for real data
                html_path = plot_plotly(csv, player, season, season_type, metric)
                try:
                    html_text = Path(html_path).read_text(encoding="utf-8")
                except Exception as e:
                    st.warning(f"NBA Stats API may be throttling for {player}. Using any cached data if available. Details: {e}")
                    continue

                st.markdown("<div class='chart-wrapper'>", unsafe_allow_html=True)
                st.components.v1.html(html_text, height=760, scrolling=True)
                st.markdown("</div>", unsafe_allow_html=True)

                # Status row
                age_min = file_age_minutes(csv)
                last_updated = f"Last updated: {age_min:.1f} min ago" if age_min is not None else "Last updated: N/A"
                data_source = "cache" if not demo_mode else "demo"
                source_label = f"Data source: {data_source}"
                st.markdown(f"<div class='status-row'>{source_label} • {last_updated}</div>", unsafe_allow_html=True)

                if not demo_mode:
                    kicked_bg_refresh = False  # This would be set in the cache logic above
                    if kicked_bg_refresh and not st.session_state.get(f"refresh_done_{player}"):
                        st.markdown("<div class='status-row'>Refreshing in background… ⏳</div>", unsafe_allow_html=True)
                    if st.session_state.get(f"refresh_done_{player}"):
                        st.info("Refreshed. Click 'Generate charts' again to load the latest.")

            except Exception as e:
                st.warning(f"NBA Stats API may be throttling for {player}. Using any cached data if available. Details: {e}")
                continue

    # reset force_refresh flag after run
    st.session_state["force_refresh"] = False

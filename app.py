from __future__ import annotations
import os, json, threading, time, re, shutil
from pathlib import Path
from typing import List
from datetime import date

import streamlit as st

from src.util import ensure_dirs, csv_path_for, html_path_for, file_age_minutes, is_stale
from src.fetch_shots import get_or_fetch_shots
from src.plot_shot_chart import plot_plotly

def recent_seasons(n: int = 15) -> list[str]:
    """Return last n NBA season labels like '2023-24', auto-derived from today's date."""
    today = date.today()
    # NBA season rolls in Oct; if we're before Oct, "current" season is last year's start
    start_year = today.year - (0 if today.month >= 10 else 1)
    seasons = []
    for i in range(n):
        y1 = start_year - i
        y2 = str((y1 + 1) % 100).zfill(2)
        seasons.append(f"{y1}-{y2}")
    return seasons


# =========================================================
# CONFIG + STYLING
# =========================================================

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
        - Uses NBA.com Stats via `nba_api`. Requests may be throttled; cloud IPs may be blocked.
        - Provide custom request headers via Streamlit secrets or env to improve reliability:
          - `.streamlit/secrets.toml`:  
            `NBA_API_HEADERS = "{\"User-Agent\":\"Mozilla/5.0\",\"x-nba-stats-origin\":\"stats\",\"Referer\":\"https://stats.nba.com/\"}"`
          - Or set env var `NBA_API_HEADERS` to the same JSON.
        - If live data fails, the app automatically shows demo visuals.
        """
    )


# =========================================================
# DEMO HANDLER (AUTO-CREATES PLACEHOLDERS)
# =========================================================

GENERIC_PNG = Path("outputs/figures/screenshot.png")
GENERIC_HTML = Path("outputs/html/demo.html")
FIG_DIR = Path("outputs/figures")
HTML_DIR = Path("outputs/html")

def safe_name(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9\s_]", "", s)
    return re.sub(r"\s+", "_", s)

def show_demo(player: str):
    """Show a player-specific demo image or HTML, auto-creating placeholder if missing."""
    player_safe = safe_name(player)
    player_png = FIG_DIR / f"{player_safe}.png"
    player_html = HTML_DIR / f"{player_safe}.html"

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    # Prefer HTML if available
    if player_html.exists():
        st.info(f"Using demo preview for {player}.")
        st.components.v1.html(player_html.read_text(encoding="utf-8"), height=760, scrolling=True)
        st.stop()

    # Create a player-specific placeholder if missing
    if not player_png.exists():
        if GENERIC_PNG.exists():
            shutil.copy2(GENERIC_PNG, player_png)
            st.info(f"Created placeholder demo for {player} (copied generic screenshot).")
        else:
            st.warning("No generic demo image found at outputs/figures/screenshot.png.")
            st.stop()

    # Display image
    st.info(f"Using demo preview for {player}.")
    st.image(str(player_png), use_container_width=True)
    st.caption("Tip: Add a custom image in outputs/figures/<player>.png for a unique demo.")
    st.stop()


# =========================================================
# HEADERS / ENV CONFIG
# =========================================================

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


# =========================================================
# CACHE + REFRESH HELPERS
# =========================================================

@st.cache_data(show_spinner=False)
def load_cached_csv(csv_path: str) -> str | None:
    return csv_path if Path(csv_path).exists() else None

def refresh_async(player: str, season: str, season_type: str, headers: dict | None):
    def _target():
        try:
            get_or_fetch_shots(player, season, season_type, headers=headers, force_refresh=True)
            st.session_state[f"refresh_done_{player}"] = True
        except Exception as e:
            st.session_state[f"refresh_err_{player}"] = str(e)
    t = threading.Thread(target=_target, daemon=True)
    t.start()


# =========================================================
# SIDEBAR CONTROLS
# =========================================================

st.sidebar.header("Controls")
players_str = st.sidebar.text_input("Player(s)", value="Stephen Curry", help='Comma-separated, e.g., "Stephen Curry, LeBron James"')
season = st.sidebar.selectbox("Season", recent_seasons(15))
season_type = st.sidebar.selectbox("Season Type", ["Regular Season", "Playoffs", "Pre Season", "All Star"])
metric = st.sidebar.radio("Metric", ["fg_pct", "frequency"], index=0)
use_cache_only = st.sidebar.checkbox("Use cache only (no live fetch)", value=False)
fresh_minutes = st.sidebar.number_input("Cache freshness (minutes)", min_value=1, max_value=10080, value=1440)
demo_mode = st.sidebar.checkbox("Demo mode (no live data)", value=True, help="Show demo previews if cache/network unavailable.")

if "force_refresh" not in st.session_state:
    st.session_state["force_refresh"] = False
if st.sidebar.button("Force refresh"):
    st.session_state["force_refresh"] = True

go = st.sidebar.button("Generate charts")


# =========================================================
# MAIN LOGIC
# =========================================================

st.title("NBA Shot Chart Visualizer")
st.caption("Interactive charts powered by NBA.com Stats via nba_api")

tabs = st.tabs(["Charts", "Compare"])
charts_tab, compare_tab = tabs

with charts_tab:
    if go:
        with st.status("Generating charts…", expanded=False) as status:
            players: List[str] = [p.strip() for p in players_str.split(",") if p.strip()]
            if not players:
                st.warning("Please enter at least one player name.")
                status.update(label="Waiting for input", state="error")
            else:
                for idx, player in enumerate(players, start=1):
                    status.write(f"Processing {player}…")
                    st.markdown(f"<div class='player-title'>{idx}. {player}</div>", unsafe_allow_html=True)
                    try:
                        csv = None
                        if not demo_mode:
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
                                    res = get_or_fetch_shots(player, season, season_type, headers=headers, force_refresh=True)
                                    if res:
                                        csv_path = res
                                        data_source = "Live-refreshed"
                                    else:
                                        st.warning(f"NBA Stats API may be throttling for {player}. Using cached data if available.")
                                else:
                                    if Path(csv_path).exists() and not stale:
                                        pass
                                    else:
                                        if Path(csv_path).exists():
                                            kicked_bg_refresh = True
                                            refresh_async(player, season, season_type, headers)
                                        else:
                                            res = get_or_fetch_shots(player, season, season_type, headers=headers, force_refresh=True)
                                            if res:
                                                csv_path = res
                                                data_source = "Live-refreshed"
                                            else:
                                                st.warning(f"NBA Stats API may be throttling for {player}. Using cached data if available.")
                                                continue

                            if not Path(csv_path).exists() or Path(csv_path).stat().st_size == 0:
                                st.warning(f"No data available for {player}. Try again later or switch networks.")
                                continue
                            csv = csv_path
                        else:
                            # DEMO MODE → auto-creates per-player placeholder
                            show_demo(player)

                        # Normal rendering (real data)
                        html_path = plot_plotly(csv, player, season, season_type, metric)
                        try:
                            html_text = Path(html_path).read_text(encoding="utf-8")
                        except Exception as e:
                            st.warning(f"NBA Stats API may be throttling for {player}. Using cached data if available. Details: {e}")
                            continue

                        st.markdown("<div class='chart-wrapper'>", unsafe_allow_html=True)
                        st.components.v1.html(html_text, height=760, scrolling=True)
                        st.markdown("</div>", unsafe_allow_html=True)

                        age_min = file_age_minutes(csv)
                        last_updated = f"Last updated: {age_min:.1f} min ago" if age_min is not None else "Last updated: N/A"
                        source_label = "cache" if not demo_mode else "demo"
                        st.markdown(f"<div class='status-row'>Data source: {source_label} • {last_updated}</div>", unsafe_allow_html=True)

                        if not demo_mode:
                            if kicked_bg_refresh and not st.session_state.get(f"refresh_done_{player}"):
                                st.markdown("<div class='status-row'>Refreshing in background… ⏳</div>", unsafe_allow_html=True)
                            if st.session_state.get(f"refresh_done_{player}"):
                                st.info("Refreshed. Click 'Generate charts' again to load the latest.")
                        
                        status.write(f"Finished {player}")
                    except Exception as e:
                        st.warning(f"NBA Stats API may be throttling for {player}. Using cached data if available. Details: {e}")
                        continue
                
                status.update(label="All charts generated", state="complete", expanded=False)

        st.session_state["force_refresh"] = False

with compare_tab:
    if st.button("Generate comparison"):
        players_cmp: List[str] = [p.strip() for p in players_str.split(",") if p.strip()]
        if not players_cmp:
            st.warning("Enter at least one player to compare.")
        else:
            # limit to first 3 for layout; can expand later
            players_cmp = players_cmp[:3]
            cols = st.columns(len(players_cmp))
            for col, player in zip(cols, players_cmp):
                with col:
                    st.markdown(f"<div class='player-title'>{player}</div>", unsafe_allow_html=True)
                    try:
                        if demo_mode:
                            # demo-first behavior
                            show_demo(player)
                        else:
                            # cache-first behavior identical to charts_tab:
                            csv_path = csv_path_for(player, season, season_type)
                            if use_cache_only:
                                if not Path(csv_path).exists() or Path(csv_path).stat().st_size == 0:
                                    st.warning("No cache found. Enable live fetch later or seed cache.")
                                    continue
                            else:
                                # try quick live fetch if missing, else fallback
                                if not Path(csv_path).exists() or Path(csv_path).stat().st_size == 0:
                                    res = get_or_fetch_shots(player, season, season_type, headers=headers, force_refresh=True)
                                    if res:
                                        csv_path = res
                            if not Path(csv_path).exists() or Path(csv_path).stat().st_size == 0:
                                show_demo(player)
                            html_path = plot_plotly(csv_path, player, season, season_type, metric)
                            html_text = Path(html_path).read_text(encoding="utf-8")
                            st.components.v1.html(html_text, height=760, scrolling=True)
                    except Exception as e:
                        st.warning(f"Could not render {player}: {e}")
                        continue
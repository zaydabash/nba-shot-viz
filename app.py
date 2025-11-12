from __future__ import annotations
import os, json, threading, time, re, shutil
from pathlib import Path
from typing import List
from datetime import date

import streamlit as st

from src.util import ensure_dirs, csv_path_for, html_path_for, file_age_minutes, is_stale
from src.fetch_shots import get_or_fetch_shots
from src.plot_shot_chart import plot_plotly
from src.predict import get_available_models, predict_for_visualization, get_model_performance

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

with st.expander("About this dashboard", expanded=False):
    st.write(
        """
        **Data Sources & Methodology**
        - **Live NBA Data**: Shot locations fetched from NBA.com Stats API via `nba_api`
        - **ShotChartDetail Endpoint**: Uses official NBA endpoint with `context_measure_simple="FGA"`
        - **No Pre-packaged Data**: All shot data fetched fresh from NBA.com
        
        **Machine Learning Models**
        - **Logistic Regression**: Fast, interpretable baseline model
        - **LightGBM**: Gradient boosting for higher accuracy (optional)
        - **Features**: Shot distance, court zones, time-based factors, shot clock
        - **Training**: Models trained on historical shot data from multiple players/seasons
        
        **Prediction Caveats**
        - Predictions are based on historical patterns and may not reflect current form
        - Model performance varies by player and shot type
        - Real-time game context (defender proximity, fatigue) not included
        - Use predictions as guidance, not absolute truth
        
        **API Reliability**
        - NBA.com Stats API may rate-limit or block cloud/shared IPs
        - Cache-first strategy minimizes API calls and improves reliability
        - Demo mode ensures dashboard works without network access
        - Background refresh keeps data current without blocking UI
        
        **Technical Details**
        - Built with Streamlit, Plotly, and scikit-learn
        - Dark theme optimized for professional presentations
        - Responsive design works on desktop and mobile
        - All code open source and well-documented
        """
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

tabs = st.tabs(["Charts", "Compare", "Predictions"])
charts_tab, compare_tab, predictions_tab = tabs

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

with predictions_tab:
    st.markdown("### Shot Prediction Analysis")
    st.markdown("View shot charts with ML-powered success probability predictions.")
    
    # Model selection
    available_models = get_available_models()
    if not available_models:
        st.warning("No trained models found. Please train models first using:")
        st.code("python -m src.train_model")
        st.stop()
    
    model_type = st.selectbox("Select Model", list(available_models.keys()), 
                              help="Choose the ML model for predictions")
    
    # Prediction controls
    col1, col2 = st.columns(2)
    with col1:
        show_predictions = st.checkbox("Show Predictions", value=True, 
                                      help="Overlay predicted probabilities on shot chart")
    with col2:
        show_performance = st.checkbox("Show Model Performance", value=True,
                                      help="Display accuracy metrics for the selected model")
    
    if st.button("Generate Predictions", key="predict_btn"):
        players_pred: List[str] = [p.strip() for p in players_str.split(",") if p.strip()]
        if not players_pred:
            st.warning("Enter at least one player to analyze.")
        else:
            for idx, player in enumerate(players_pred, start=1):
                st.markdown(f"<div class='player-title'>{idx}. {player} - Predictions</div>", unsafe_allow_html=True)
                
                try:
                    # Get data
                    csv_path = csv_path_for(player, season, season_type)
                    if not Path(csv_path).exists() or Path(csv_path).stat().st_size == 0:
                        if demo_mode:
                            st.info("Demo mode: Using sample predictions")
                            # Create sample prediction data
                            import pandas as pd
                            import numpy as np
                            sample_data = pd.DataFrame({
                                'LOC_X': np.random.normal(0, 100, 50),
                                'LOC_Y': np.random.uniform(50, 200, 50),
                                'SHOT_MADE_FLAG': np.random.choice([0, 1], 50),
                                'predicted_probability': np.random.uniform(0.2, 0.8, 50),
                                'predicted_made': np.random.choice([True, False], 50),
                                'prediction_confidence': np.random.uniform(0.1, 0.9, 50)
                            })
                        else:
                            st.warning(f"No data found for {player}. Try refreshing or check cache.")
                            continue
                    else:
                        # Load real data and make predictions
                        import pandas as pd
                        df = pd.read_csv(csv_path)
                        
                        if show_predictions:
                            df_with_pred = predict_for_visualization(df, player, model_type)
                        else:
                            df_with_pred = df.copy()
                            df_with_pred['predicted_probability'] = 0.5
                            df_with_pred['predicted_made'] = False
                            df_with_pred['prediction_confidence'] = 0.0
                    
                    # Create enhanced plotly chart with predictions
                    if show_predictions and 'predicted_probability' in df_with_pred.columns:
                        # Create prediction-enhanced visualization
                        import plotly.graph_objects as go
                        import plotly.express as px
                        
                        # Bin the data for visualization
                        bin_size = 15
                        df_with_pred['bin_x'] = ((df_with_pred['LOC_X'] + 250) // bin_size).astype(int)
                        df_with_pred['bin_y'] = (df_with_pred['LOC_Y'] // bin_size).astype(int)
                        df_with_pred['bin_center_x'] = df_with_pred['bin_x'] * bin_size - 250 + bin_size / 2
                        df_with_pred['bin_center_y'] = df_with_pred['bin_y'] * bin_size + bin_size / 2
                        
                        # Calculate bin statistics
                        bin_stats = df_with_pred.groupby(['bin_x', 'bin_y', 'bin_center_x', 'bin_center_y']).agg({
                            'SHOT_MADE_FLAG': ['count', 'mean'],
                            'predicted_probability': 'mean',
                            'prediction_confidence': 'mean'
                        }).reset_index()
                        
                        bin_stats.columns = ['bin_x', 'bin_y', 'bin_center_x', 'bin_center_y', 
                                           'attempts', 'actual_fg_pct', 'predicted_prob', 'avg_confidence']
                        
                        # Filter bins with sufficient attempts
                        bin_stats = bin_stats[bin_stats['attempts'] >= 3]
                        
                        # Create figure
                        fig = go.Figure()
                        
                        # Add prediction overlay
                        fig.add_trace(go.Scattergl(
                            x=bin_stats['bin_center_x'],
                            y=bin_stats['bin_center_y'],
                            mode='markers',
                            marker=dict(
                                size=bin_stats['attempts'] * 2,
                                color=bin_stats['predicted_prob'],
                                colorscale='RdYlGn',
                                opacity=0.7,
                                line=dict(width=1, color='white'),
                                showscale=True,
                                colorbar=dict(title="Predicted<br>Success Rate")
                            ),
                            hovertemplate=(
                                "Location: (%{x:.0f}, %{y:.0f})<br>" +
                                "Attempts: %{customdata[0]}<br>" +
                                "Actual FG%: %{customdata[1]:.2f}<br>" +
                                "Predicted Success: %{customdata[2]:.2f}<br>" +
                                "Confidence: %{customdata[3]:.2f}<extra></extra>"
                            ),
                            customdata=list(zip(bin_stats['attempts'], bin_stats['actual_fg_pct'], 
                                              bin_stats['predicted_prob'], bin_stats['avg_confidence'])),
                            name="Predictions"
                        ))
                        
                        # Add court shapes
                        court_shapes = [
                            dict(type="rect", x0=-250, y0=0, x1=250, y1=470, line=dict(color="#e6e6e6", width=1.2), fillcolor="rgba(0,0,0,0)"),
                            dict(type="rect", x0=-80, y0=0, x1=80, y1=190, line=dict(color="#e6e6e6", width=1.2), fillcolor="rgba(0,0,0,0)"),
                            dict(type="circle", x0=-60, y0=130, x1=60, y1=250, line=dict(color="#e6e6e6", width=1.2), fillcolor="rgba(0,0,0,0)"),
                            dict(type="path", path="M -40,60 A 40,40 0 0,1 40,60", line=dict(color="#e6e6e6", width=1.2), fillcolor="rgba(0,0,0,0)"),
                            dict(type="rect", x0=-30, y0=40, x1=30, y1=41, line=dict(color="#e6e6e6", width=1.2), fillcolor="#e6e6e6"),
                            dict(type="circle", x0=-7.5, y0=52.5, x1=7.5, y1=67.5, line=dict(color="#e6e6e6", width=1.2), fillcolor="rgba(0,0,0,0)"),
                            dict(type="path", path="M -220,0 L -220,140 A 237.5,237.5 0 0,1 220,140 L 220,0", line=dict(color="#e6e6e6", width=1.2), fillcolor="rgba(0,0,0,0)"),
                        ]
                        
                        fig.update_layout(
                            template=None,
                            paper_bgcolor="#0f1115",
                            plot_bgcolor="#0f1115",
                            font=dict(family="Inter, Helvetica, Arial, sans-serif", size=13, color="#e6e6e6"),
                            margin=dict(l=20, r=20, t=70, b=20),
                            width=980,
                            height=720,
                            title=dict(
                                text=f"{player} — {season} ({season_type})<br><sub>ML-Powered Shot Success Predictions</sub>",
                                x=0.5,
                                xanchor="center",
                                font=dict(size=20, color="#ffffff")
                            ),
                            showlegend=False,
                            shapes=court_shapes
                        )
                        
                        # Save and display
                        pred_html_path = f"outputs/html/{player}_{season}_{season_type}_predictions_{model_type}.html"
                        ensure_dirs("outputs/html")
                        fig.write_html(pred_html_path, include_plotlyjs="cdn", full_html=True, 
                                      config={"responsive": True})
                        
                        st.components.v1.html(fig.to_html(include_plotlyjs="cdn"), height=760, scrolling=True)
                        
                    else:
                        # Fallback to regular chart
                        html_path = plot_plotly(csv_path, player, season, season_type, metric)
                        html_text = Path(html_path).read_text(encoding="utf-8")
                        st.components.v1.html(html_text, height=760, scrolling=True)
                    
                    # Show model performance
                    if show_performance and not demo_mode and Path(csv_path).exists():
                        try:
                            performance = get_model_performance(df, player, model_type)
                            if "error" not in performance:
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Accuracy", f"{performance['accuracy']:.1%}")
                                with col2:
                                    st.metric("ROC AUC", f"{performance['roc_auc']:.3f}")
                                with col3:
                                    st.metric("MAE", f"{performance['mae']:.3f}")
                            else:
                                st.warning(f"Performance calculation failed: {performance['error']}")
                        except Exception as e:
                            st.warning(f"Could not calculate performance: {e}")
                    
                    # Data freshness info
                    if not demo_mode and Path(csv_path).exists():
                        age_min = file_age_minutes(csv_path)
                        last_updated = f"Last updated: {age_min:.1f} min ago" if age_min is not None else "Last updated: N/A"
                        st.markdown(f"<div class='status-row'>Data source: cache • {last_updated}</div>", unsafe_allow_html=True)
                
                except Exception as e:
                    st.warning(f"Error processing {player}: {e}")
                    continue
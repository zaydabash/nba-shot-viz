from __future__ import annotations
import time
import os
import json
from typing import Optional
import pandas as pd
import numpy as np
from rich import print
from slugify import slugify

from nba_api.stats.endpoints import shotchartdetail
from nba_api.stats.static import players
from requests.exceptions import ReadTimeout, ConnectionError, HTTPError

from .util import get_headers, get_proxy, ensure_dirs, csv_path_for

def resolve_player_id(player_name: str) -> int:
    matches = players.find_players_by_full_name(player_name)
    if not matches:
        raise ValueError(f"No player found for '{player_name}'")
    # Prefer exact full-name match if present
    for m in matches:
        if m.get("full_name","").lower() == player_name.lower():
            return int(m["id"])
    return int(matches[0]["id"])

def _resolve_headers(passed_headers) -> Optional[dict]:
    # 1) Function arg
    if isinstance(passed_headers, dict):
        return passed_headers
    if passed_headers is not None:
        return passed_headers
    # 2) Env var JSON
    env_raw = os.getenv("NBA_API_HEADERS")
    if env_raw:
        try:
            return json.loads(env_raw)
        except Exception:
            pass
    # 3) Streamlit secrets (optional)
    try:
        import streamlit as st  # type: ignore
        raw = st.secrets.get("NBA_API_HEADERS", None)
        if raw:
            return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        pass
    return None

def _resolve_proxy(passed_proxy) -> Optional[dict]:
    proxy_url = os.getenv("PROXY_URL")
    if proxy_url:
        return {"http": proxy_url, "https": proxy_url}
    # fallback to util proxy if provided
    if passed_proxy:
        if isinstance(passed_proxy, str):
            return {"http": passed_proxy, "https": passed_proxy}
        return passed_proxy
    return None

def enhance_shot_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enhance shot chart data with additional features for ML.
    
    Args:
        df: Raw shot chart DataFrame from NBA API
    
    Returns:
        Enhanced DataFrame with additional features
    """
    if df is None or df.empty:
        return df
    
    df = df.copy()
    
    # Ensure we have the basic required columns
    if 'LOC_X' not in df.columns or 'LOC_Y' not in df.columns:
        print("[yellow]Warning: Missing LOC_X or LOC_Y columns[/yellow]")
        return df
    
    # Add shot distance and angle
    df['SHOT_DISTANCE'] = ((df['LOC_X']**2 + df['LOC_Y']**2)**0.5).round(1)
    df['SHOT_ANGLE'] = (np.arctan2(df['LOC_Y'], df['LOC_X']) * 180 / np.pi).round(1)
    
    # Add court zone information
    df['IS_PAINT'] = (df['LOC_X'].abs() <= 80) & (df['LOC_Y'] <= 190)
    df['IS_CORNER_3'] = (df['LOC_X'].abs() >= 220) & (df['LOC_Y'] <= 140)
    df['IS_ABOVE_BREAK_3'] = (df['SHOT_DISTANCE'] >= 237.5) & (~df['IS_CORNER_3'])
    df['IS_MIDRANGE'] = (~df['IS_PAINT']) & (~df['IS_CORNER_3']) & (~df['IS_ABOVE_BREAK_3'])
    
    # Add shot type based on distance
    df['SHOT_TYPE'] = 'Paint'
    df.loc[df['IS_CORNER_3'], 'SHOT_TYPE'] = 'Corner 3'
    df.loc[df['IS_ABOVE_BREAK_3'], 'SHOT_TYPE'] = 'Above Break 3'
    df.loc[df['IS_MIDRANGE'], 'SHOT_TYPE'] = 'Midrange'
    
    # Add time-based features if available
    if 'PERIOD' in df.columns:
        df['IS_LATE_GAME'] = df['PERIOD'] >= 4
        df['IS_OVERTIME'] = df['PERIOD'] > 4
    else:
        df['IS_LATE_GAME'] = False
        df['IS_OVERTIME'] = False
    
    # Add shot clock features if available
    if 'SHOT_CLOCK' in df.columns:
        df['SHOT_CLOCK_LOW'] = df['SHOT_CLOCK'] <= 5
        df['SHOT_CLOCK_HIGH'] = df['SHOT_CLOCK'] >= 20
    else:
        df['SHOT_CLOCK_LOW'] = False
        df['SHOT_CLOCK_HIGH'] = False
    
    # Add game situation features if available
    if 'GAME_CLOCK' in df.columns:
        # Parse game clock to seconds remaining
        try:
            df['GAME_CLOCK_SECONDS'] = df['GAME_CLOCK'].str.extract(r'(\d+):(\d+)')
            df['GAME_CLOCK_SECONDS'] = df['GAME_CLOCK_SECONDS'].apply(
                lambda x: int(x[0]) * 60 + int(x[1]) if pd.notna(x[0]) and pd.notna(x[1]) else 0
            )
            df['IS_CLUTCH_TIME'] = df['GAME_CLOCK_SECONDS'] <= 120  # Last 2 minutes
        except:
            df['GAME_CLOCK_SECONDS'] = 0
            df['IS_CLUTCH_TIME'] = False
    else:
        df['GAME_CLOCK_SECONDS'] = 0
        df['IS_CLUTCH_TIME'] = False
    
    return df


def _call_shotchart(player_id: int, season: str, season_type: str, headers, proxy) -> Optional[pd.DataFrame]:
    """Call NBA stats ShotChartDetail with retries and jitter. Returns DataFrame or None."""
    resolved_headers = _resolve_headers(headers)
    resolved_proxy = _resolve_proxy(proxy)

    import random
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            # small jitter between tries
            time.sleep(random.uniform(0.4, 0.8))
            resp = shotchartdetail.ShotChartDetail(
                team_id=0,
                player_id=player_id,
                season_nullable=season,
                season_type_all_star=season_type,
                context_measure_simple="FGA",
                headers=resolved_headers,
                proxy=resolved_proxy,
                timeout=60,
            )
            df = resp.get_data_frames()[0]
            if df is None or df.empty:
                print(f"[yellow]empty response for player_id={player_id} {season} ({season_type})[/yellow]")
                return None
            if "SHOT_MADE_FLAG" in df.columns:
                df["SHOT_MADE_FLAG"] = df["SHOT_MADE_FLAG"].astype(int)
            # Enhance with additional features for ML
            df = enhance_shot_data(df)
            return df
        except (ReadTimeout, ConnectionError, HTTPError) as e:
            sleep_for = random.uniform(0.4, 0.8)
            print(f"[yellow]attempt {attempt}/{max_attempts} failed ({type(e).__name__}): {e}. backing off {sleep_for:.1f}s...[/yellow]")
            if attempt == max_attempts:
                return None
            time.sleep(sleep_for)
        except Exception as e:
            sleep_for = random.uniform(0.4, 0.8)
            print(f"[yellow]attempt {attempt}/{max_attempts} failed ({type(e).__name__}): {e}. backing off {sleep_for:.1f}s...[/yellow]")
            if attempt == max_attempts:
                return None
            time.sleep(sleep_for)
    return None

def fetch_and_cache(player_name: str, season: str, season_type: str="Regular Season") -> str:
    headers = get_headers()
    proxy = get_proxy()
    pid = resolve_player_id(player_name)
    df = _call_shotchart(pid, season, season_type, headers, proxy)

    out_path = f"data/raw/{slugify(player_name)}_{season.replace(' ','_')}_{slugify(season_type)}.csv"

    # On failure, write an empty CSV with expected columns to keep downstream flow intact
    if df is None or df.empty:
        print(f"[yellow]No shots fetched for {player_name} {season} ({season_type}). Writing empty CSV.[/yellow]")
        empty_df = pd.DataFrame({
            "LOC_X": pd.Series(dtype=float),
            "LOC_Y": pd.Series(dtype=float),
            "SHOT_MADE_FLAG": pd.Series(dtype=int),
        })
        empty_df.to_csv(out_path, index=False)
        time.sleep(0.5)
        return out_path

    # Keep offensive half only & sane bounds
    df = df[(df["LOC_Y"] >= 0) & (df["LOC_Y"] <= 470) &
            (df["LOC_X"].between(-250, 250))]
    df.to_csv(out_path, index=False)
    print(f"[bold green]Saved {len(df)} shots → {out_path}[/bold green]")
    time.sleep(1.0)  # be polite
    return out_path

# New cache-first wrapper

def get_or_fetch_shots(player: str, season: str, season_type: str, *, headers: dict | None = None, force_refresh: bool = False) -> str | None:
    """
    Returns CSV path for (player, season, season_type).
    If force_refresh=False and a CSV exists, return it immediately.
    If missing/stale OR force_refresh=True, try to fetch and update the CSV.
    On failure, keep the old CSV (if any) and return that path.
    Returns None only if no cache exists and fetch fails.
    """
    ensure_dirs("data/raw")
    csv_path = csv_path_for(player, season, season_type)

    # If not forcing refresh and cache exists, return immediately
    if not force_refresh and os.path.exists(csv_path):
        return csv_path

    # Otherwise, try to fetch
    proxy = get_proxy()
    try:
        pid = resolve_player_id(player)
        df = _call_shotchart(pid, season, season_type, headers, proxy)
    except Exception as e:
        print(f"[yellow]fetch error: {e}. returning cached (if any).[/yellow]")
        return csv_path if os.path.exists(csv_path) else None

    if df is None or df.empty:
        print(f"[yellow]no data fetched for {player} {season} ({season_type}). returning cached (if any).[/yellow]")
        return csv_path if os.path.exists(csv_path) else None

    # Keep offensive half only & sane bounds, then write
    df = df[(df["LOC_Y"] >= 0) & (df["LOC_Y"] <= 470) & (df["LOC_X"].between(-250, 250))]
    pd.DataFrame(df).to_csv(csv_path, index=False)
    return csv_path

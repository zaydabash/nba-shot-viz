from __future__ import annotations
import time
from typing import Optional
import pandas as pd
from rich import print
from slugify import slugify
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from nba_api.stats.endpoints import shotchartdetail
from nba_api.stats.static import players
from requests.exceptions import ReadTimeout, ConnectionError

from .util import get_headers, get_proxy

def resolve_player_id(player_name: str) -> int:
    matches = players.find_players_by_full_name(player_name)
    if not matches:
        raise ValueError(f"No player found for '{player_name}'")
    # Prefer exact full-name match if present
    for m in matches:
        if m.get("full_name","").lower() == player_name.lower():
            return int(m["id"])
    return int(matches[0]["id"])

@retry(stop=stop_after_attempt(6),
       wait=wait_exponential(multiplier=1, min=1, max=30),
       retry=retry_if_exception_type((ReadTimeout, ConnectionError)))
def _call_shotchart(player_id: int, season: str, season_type: str, headers, proxy) -> pd.DataFrame:
    # Add jitter sleep between requests (1-2 seconds)
    import random
    time.sleep(random.uniform(1.0, 2.0))
    
    # context_measure_simple='FGA' ensures made+missed attempts are returned.
    # team_id=0 yields all shots for that player (across teams in that season).
    resp = shotchartdetail.ShotChartDetail(
        team_id=0,
        player_id=player_id,
        season_nullable=season,
        season_type_all_star=season_type,
        context_measure_simple="FGA",
        headers=headers,
        proxy=proxy,
        timeout=30
    )
    df = resp.get_data_frames()[0]
    # Normalize expected columns
    if "SHOT_MADE_FLAG" in df.columns:
        df["SHOT_MADE_FLAG"] = df["SHOT_MADE_FLAG"].astype(int)
    return df

def fetch_and_cache(player_name: str, season: str, season_type: str="Regular Season") -> str:
    headers = get_headers()
    proxy = get_proxy()
    pid = resolve_player_id(player_name)
    df = _call_shotchart(pid, season, season_type, headers, proxy)

    # Keep offensive half only & sane bounds
    df = df[(df["LOC_Y"] >= 0) & (df["LOC_Y"] <= 470) &
            (df["LOC_X"].between(-250, 250))]
    out_path = f"data/raw/{slugify(player_name)}_{season.replace(' ','_')}_{slugify(season_type)}.csv"
    df.to_csv(out_path, index=False)
    print(f"[bold green]Saved {len(df)} shots → {out_path}[/bold green]")
    time.sleep(1.0)  # be polite
    return out_path

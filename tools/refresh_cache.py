#!/usr/bin/env python3
"""
Cache pre-warm tool for NBA shot data.

Usage:
  PLAYERS="Stephen Curry,LeBron James,Giannis Antetokounmpo" \
  python tools/refresh_cache.py --season "2023-24" --season_type "Regular Season" --metric fg_pct --force

- Reads players from PLAYERS env var (comma separated) or defaults to:
  ["Stephen Curry", "LeBron James", "Giannis Antetokounmpo"]
- Fetches and caches player shot data without plotting.
- Intended to be run before interactive use to reduce latency and API hits.
"""

from __future__ import annotations
import os, sys, json, argparse
from typing import List

# Attempt to add project root to path when executed directly
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.fetch_shots import get_or_fetch_shots


def parse_players_env() -> List[str]:
    raw = os.getenv("PLAYERS", "")
    if not raw.strip():
        return ["Stephen Curry", "LeBron James", "Giannis Antetokounmpo"]
    return [p.strip() for p in raw.split(",") if p.strip()]


def resolve_headers() -> dict | None:
    # Streamlit secrets (optional)
    try:
        import streamlit as st  # type: ignore
        secret_raw = st.secrets.get("NBA_API_HEADERS", None)
        if secret_raw:
            return json.loads(secret_raw) if isinstance(secret_raw, str) else secret_raw
    except Exception:
        pass
    # Env var fallback
    env_raw = os.getenv("NBA_API_HEADERS")
    if env_raw:
        try:
            return json.loads(env_raw)
        except Exception:
            pass
    return None


def main():
    parser = argparse.ArgumentParser(description="Pre-warm shot data cache for players")
    parser.add_argument("--season", required=True, help='e.g., "2023-24"')
    parser.add_argument("--season_type", default="Regular Season", choices=["Regular Season","Playoffs","Pre Season","All Star"])
    parser.add_argument("--metric", default="fg_pct", choices=["fg_pct","frequency"])  # accepted but unused here
    parser.add_argument("--force", action="store_true", help="Force refresh from network")
    args = parser.parse_args()

    players = parse_players_env()
    headers = resolve_headers()

    print(f"Pre-warming cache for {len(players)} player(s): {', '.join(players)}")
    for idx, player in enumerate(players, 1):
        print(f"[{idx}/{len(players)}] {player} — {args.season} ({args.season_type})")
        try:
            path = get_or_fetch_shots(player, args.season, args.season_type, headers=headers, force_refresh=args.force)
            if path and os.path.exists(path) and os.path.getsize(path) > 0:
                print(f"  Cached CSV → {path}")
            elif path and os.path.exists(path):
                print(f"  Cached (empty) CSV → {path}")
            else:
                print(f"  Failed to cache shots for {player}")
        except Exception as e:
            print(f"  Error: {e}")


if __name__ == "__main__":
    main()

"""
Auto-refresh tool for NBA shot data

This script provides scheduled or on-demand data updates to keep the dashboard current.
"""

from __future__ import annotations
import os
import time
import schedule
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import json

from src.fetch_shots import get_or_fetch_shots
from src.util import ensure_dirs, file_age_minutes, is_stale


def get_default_players() -> List[str]:
    """Get default list of players to refresh."""
    env_players = os.getenv("NBA_PLAYERS")
    if env_players:
        return [p.strip() for p in env_players.split(",")]
    
    return [
        "Stephen Curry", "LeBron James", "Kevin Durant", "Giannis Antetokounmpo",
        "Luka Doncic", "Jayson Tatum", "Joel Embiid", "Nikola Jokic",
        "Damian Lillard", "Kawhi Leonard", "Paul George", "Jimmy Butler"
    ]


def get_default_seasons() -> List[str]:
    """Get default list of seasons to refresh."""
    from datetime import date
    today = date.today()
    start_year = today.year - (0 if today.month >= 10 else 1)
    
    seasons = []
    for i in range(3):  # Last 3 seasons
        y1 = start_year - i
        y2 = str((y1 + 1) % 100).zfill(2)
        seasons.append(f"{y1}-{y2}")
    
    return seasons


def resolve_headers() -> Optional[dict]:
    """Resolve headers from environment or secrets."""
    # Try environment variable first
    env_raw = os.getenv("NBA_API_HEADERS")
    if env_raw:
        try:
            return json.loads(env_raw)
        except Exception:
            pass
    
    # Try Streamlit secrets (if available)
    try:
        import streamlit as st
        raw = st.secrets.get("NBA_API_HEADERS", None)
        if raw:
            return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        pass
    
    return None


def refresh_player_data(player: str, season: str, season_type: str, 
                       headers: Optional[dict] = None, force: bool = False) -> bool:
    """
    Refresh data for a single player.
    
    Args:
        player: Player name
        season: Season (e.g., "2023-24")
        season_type: Season type (e.g., "Regular Season")
        headers: API headers
        force: Force refresh even if data is fresh
    
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"Refreshing {player} ({season} {season_type})...")
        
        # Check if we need to refresh
        if not force:
            csv_path = get_or_fetch_shots(player, season, season_type, headers=headers, force_refresh=False)
            if csv_path and not is_stale(csv_path, max_minutes=60):  # 1 hour freshness
                print(f"  Data is fresh, skipping {player}")
                return True
        
        # Fetch new data
        csv_path = get_or_fetch_shots(player, season, season_type, headers=headers, force_refresh=True)
        
        if csv_path and Path(csv_path).exists() and Path(csv_path).stat().st_size > 0:
            print(f"  Successfully refreshed {player}")
            return True
        else:
            print(f"  Failed to refresh {player}")
            return False
            
    except Exception as e:
        print(f"  Error refreshing {player}: {e}")
        return False


def refresh_all_data(players: List[str], seasons: List[str], season_types: List[str],
                    headers: Optional[dict] = None, force: bool = False) -> dict:
    """
    Refresh data for all players/seasons/season_types.
    
    Args:
        players: List of player names
        seasons: List of seasons
        season_types: List of season types
        headers: API headers
        force: Force refresh even if data is fresh
    
    Returns:
        Dictionary with refresh results
    """
    results = {
        "successful": 0,
        "failed": 0,
        "skipped": 0,
        "total": 0
    }
    
    total_combinations = len(players) * len(seasons) * len(season_types)
    print(f"Refreshing {total_combinations} player/season combinations...")
    
    for player in players:
        for season in seasons:
            for season_type in season_types:
                results["total"] += 1
                
                success = refresh_player_data(player, season, season_type, headers, force)
                
                if success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                
                # Small delay between requests to avoid rate limiting
                time.sleep(1)
    
    return results


def scheduled_refresh():
    """Scheduled refresh function for cron-like behavior."""
    print(f"\n=== Scheduled Refresh - {datetime.now()} ===")
    
    players = get_default_players()
    seasons = get_default_seasons()
    season_types = ["Regular Season"]
    headers = resolve_headers()
    
    results = refresh_all_data(players, seasons, season_types, headers, force=False)
    
    print(f"Refresh complete: {results['successful']} successful, {results['failed']} failed")
    return results


def main():
    """CLI entry point for auto-refresh."""
    parser = argparse.ArgumentParser(description="Auto-refresh NBA shot data")
    parser.add_argument("--players", nargs="+", help="Players to refresh")
    parser.add_argument("--seasons", nargs="+", help="Seasons to refresh")
    parser.add_argument("--season-types", nargs="+", help="Season types to refresh")
    parser.add_argument("--force", action="store_true", help="Force refresh even if data is fresh")
    parser.add_argument("--schedule", choices=["hourly", "daily", "weekly"], 
                       help="Schedule automatic refreshes")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    
    args = parser.parse_args()
    
    # Set up directories
    ensure_dirs("data/raw", "logs")
    
    # Get parameters
    players = args.players or get_default_players()
    seasons = args.seasons or get_default_seasons()
    season_types = args.season_types or ["Regular Season"]
    headers = resolve_headers()
    
    print(f"Auto-refresh starting...")
    print(f"Players: {players}")
    print(f"Seasons: {seasons}")
    print(f"Season types: {season_types}")
    print(f"Force refresh: {args.force}")
    
    if args.schedule:
        print(f"Scheduling {args.schedule} refreshes...")
        
        if args.schedule == "hourly":
            schedule.every().hour.do(scheduled_refresh)
        elif args.schedule == "daily":
            schedule.every().day.at("06:00").do(scheduled_refresh)
        elif args.schedule == "weekly":
            schedule.every().monday.at("06:00").do(scheduled_refresh)
        
        print("Scheduler started. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            print("\nScheduler stopped.")
    
    elif args.once:
        # Run once
        results = refresh_all_data(players, seasons, season_types, headers, args.force)
        
        print(f"\nRefresh complete:")
        print(f"  Successful: {results['successful']}")
        print(f"  Failed: {results['failed']}")
        print(f"  Total: {results['total']}")
        
        if results['failed'] > 0:
            return 1
    
    else:
        print("Use --once to run once or --schedule to run continuously")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

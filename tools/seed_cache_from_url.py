#!/usr/bin/env python3
"""
Seed cache from a CSV URL.

Usage:
  python tools/seed_cache_from_url.py --player "Stephen Curry" --season "2023-24" --season_type "Regular Season" --url "https://example.com/shots.csv" --force

Downloads CSV from URL to standard cache path in data/raw/.
Useful for seeding cache with pre-fetched data or avoiding API rate limits.
"""

from __future__ import annotations
import os, sys, argparse
import requests
from pathlib import Path

# Add project root to path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.util import ensure_dirs, csv_path_for


def main():
    parser = argparse.ArgumentParser(description="Seed cache from CSV URL")
    parser.add_argument("--player", required=True, help='e.g., "Stephen Curry"')
    parser.add_argument("--season", required=True, help='e.g., "2023-24"')
    parser.add_argument("--season_type", default="Regular Season", choices=["Regular Season","Playoffs","Pre Season","All Star"])
    parser.add_argument("--url", required=True, help="URL to CSV file")
    parser.add_argument("--force", action="store_true", help="Overwrite existing file")
    args = parser.parse_args()

    csv_path = csv_path_for(args.player, args.season, args.season_type)
    
    if Path(csv_path).exists() and not args.force:
        print(f"File already exists: {csv_path}")
        print("Use --force to overwrite")
        return

    print(f"Downloading {args.url} → {csv_path}")
    try:
        response = requests.get(args.url, timeout=30)
        response.raise_for_status()
        
        ensure_dirs("data/raw")
        Path(csv_path).write_text(response.text, encoding="utf-8")
        
        size = Path(csv_path).stat().st_size
        print(f"✓ Downloaded {size} bytes → {csv_path}")
        
    except requests.RequestException as e:
        print(f"✗ Download failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

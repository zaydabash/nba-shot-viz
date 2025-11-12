#!/usr/bin/env python3
"""
Seed cache from a CSV URL.

Usage:
  python tools/seed_cache_from_url.py --player "Stephen Curry" --season "2023-24" --season_type "Regular Season" --url "https://example.com/shots.csv" --force

Downloads CSV from URL to standard cache path in data/raw/.
Useful for seeding cache with pre-fetched data or avoiding API rate limits.
"""

from __future__ import annotations
import os
import sys
import argparse
import requests
from pathlib import Path
from urllib.parse import urlparse

# Add project root to path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.util import ensure_dirs, csv_path_for


def validate_url(url: str) -> bool:
    """Validate URL is safe to download from."""
    try:
        parsed = urlparse(url)
        # Only allow http and https schemes
        if parsed.scheme not in ('http', 'https'):
            return False
        # Prefer HTTPS for security
        if parsed.scheme == 'http':
            print("Warning: Using HTTP instead of HTTPS. Consider using HTTPS for security.")
        # Basic validation - URL must have netloc
        if not parsed.netloc:
            return False
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Seed cache from CSV URL")
    parser.add_argument("--player", required=True, help='e.g., "Stephen Curry"')
    parser.add_argument("--season", required=True, help='e.g., "2023-24"')
    parser.add_argument("--season_type", default="Regular Season",
                       choices=["Regular Season", "Playoffs", "Pre Season", "All Star"])
    parser.add_argument("--url", required=True, help="URL to CSV file (HTTPS recommended)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing file")
    args = parser.parse_args()

    # Validate URL
    if not validate_url(args.url):
        print(f"Error: Invalid or unsafe URL: {args.url}")
        print("URL must be HTTP or HTTPS and have a valid domain")
        sys.exit(1)

    # Validate and sanitize output path
    csv_path = csv_path_for(args.player, args.season, args.season_type)
    # Ensure path is within project directory (prevent directory traversal)
    csv_path_abs = os.path.abspath(csv_path)
    project_root = os.path.abspath(ROOT)
    if not csv_path_abs.startswith(project_root):
        print(f"Error: Invalid output path: {csv_path}")
        sys.exit(1)

    if Path(csv_path).exists() and not args.force:
        print(f"File already exists: {csv_path}")
        print("Use --force to overwrite")
        return

    print(f"Downloading {args.url} → {csv_path}")
    try:
        # Validate content type if available
        response = requests.get(args.url, timeout=30, stream=True)
        response.raise_for_status()
        
        # Check content type (optional, but good practice)
        content_type = response.headers.get('content-type', '')
        if content_type and 'text/csv' not in content_type and 'text/plain' not in content_type:
            print(f"Warning: Unexpected content type: {content_type}")
        
        # Read response content
        content = response.text
        
        # Basic validation - ensure it's not empty
        if not content or len(content.strip()) == 0:
            print("Error: Downloaded file is empty")
            sys.exit(1)
        
        ensure_dirs("data/raw")
        Path(csv_path).write_text(content, encoding="utf-8")
        
        size = Path(csv_path).stat().st_size
        print(f"Downloaded {size} bytes → {csv_path}")
        
    except requests.RequestException as e:
        print(f"Download failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

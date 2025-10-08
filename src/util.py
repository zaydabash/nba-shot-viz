from __future__ import annotations
import json, os
from typing import Dict, Optional
from pathlib import Path
import time
from slugify import slugify

def get_headers() -> Optional[Dict[str, str]]:
    """
    Optional custom headers for NBA stats endpoints. Set NBA_API_HEADERS as JSON.
    Example:
      export NBA_API_HEADERS='{"User-Agent":"Mozilla/5.0","x-nba-stats-origin":"stats","Referer":"https://stats.nba.com/"}'
    """
    raw = os.getenv("NBA_API_HEADERS")
    if not raw:
        return None
    try:
        hdrs = json.loads(raw)
        assert isinstance(hdrs, dict)
        return {str(k): str(v) for k, v in hdrs.items()}
    except Exception:
        return None

def get_proxy() -> Optional[str]:
    """
    Optional single proxy URL in env NBA_API_PROXY. Example:
      export NBA_API_PROXY="http://user:pass@host:port"
    """
    return os.getenv("NBA_API_PROXY")

# New helpers

def ensure_dirs(*dirs: str) -> None:
    """Create any missing directories."""
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)

def csv_path_for(player: str, season: str, season_type: str) -> str:
    """Stable CSV path under data/raw/ following slug conventions."""
    p = slugify(player)
    s = season.replace(' ', '_')
    stype = slugify(season_type)
    return str(Path("data/raw") / f"{p}_{s}_{stype}.csv")

def html_path_for(player: str, season: str, season_type: str, metric: str) -> str:
    """Stable HTML path under outputs/html/ following slug conventions."""
    p = slugify(player)
    s = season.replace(' ', '_')
    stype = slugify(season_type)
    m = slugify(metric)
    return str(Path("outputs/html") / f"{p}_{s}_{stype}_{m}.html")

def file_age_minutes(path: str) -> Optional[float]:
    """Return minutes since last modified, or None if missing."""
    try:
        stat = Path(path).stat()
    except FileNotFoundError:
        return None
    now = time.time()
    age_seconds = max(0.0, now - stat.st_mtime)
    return age_seconds / 60.0

def is_stale(path: str, max_minutes: float = 1440) -> bool:
    """True if missing or older than max_minutes."""
    age = file_age_minutes(path)
    if age is None:
        return True
    return age > max_minutes

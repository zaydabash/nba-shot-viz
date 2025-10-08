from __future__ import annotations
import json, os
from typing import Dict, Optional

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

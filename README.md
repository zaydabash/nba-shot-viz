# NBA Shot Chart Visualizer (Real NBA.com Data)

## 📊 Preview

<div align="center">
  <img src="outputs/figures/screenshot.png" alt="NBA Shot Chart Preview" width="900">
</div>

This repo pulls **real** shot locations from the NBA.com Stats API (via `nba_api`) and renders a clean, professional half-court **hexbin** shot chart for either **frequency** or **efficiency (FG%)**.

**Highlights**
- Real-time fetch from `ShotChartDetail` with `context_measure_simple="FGA"` (includes makes & misses).
- NBA coordinate-accurate half court overlay.
- One-command CLI. Outputs high-res PNG (and easy to extend to Plotly HTML).
- Robust to common NBA Stats quirks (headers/proxy/timeouts).

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pip install --upgrade pip

# Optional if your IP needs it:
# export NBA_API_HEADERS='{"User-Agent":"Mozilla/5.0","x-nba-stats-origin":"stats","Referer":"https://stats.nba.com/"}'
# export NBA_API_PROXY="http://user:pass@host:port"

python src/cli.py --player "Stephen Curry" --season "2023-24" --season_type "Regular Season" --metric fg_pct
```

## Interactive Version

For interactive shot charts with hover details and zoom capabilities, use the `plot_plotly()` function:

```python
from src.plot_shot_chart import plot_plotly
from src.fetch_shots import fetch_and_cache

# Fetch data
csv_path = fetch_and_cache("Stephen Curry", "2023-24", "Regular Season")

# Create interactive HTML chart
html_path = plot_plotly(csv_path, "Stephen Curry", "2023-24", "Regular Season")
print(f"Interactive chart saved → {html_path}")
```

**Features:**
- **Hover details**: See exact shot coordinates and make/miss status
- **Zoom & pan**: Explore specific court areas in detail
- **Toggle layers**: Show/hide made vs missed shots
- **Responsive**: Works on desktop and mobile browsers
- **Self-contained**: HTML files include all dependencies

Interactive charts are saved to `outputs/html/` and can be opened in any web browser.

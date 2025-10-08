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

### Interactive (Plotly)

Generate an interactive HTML chart you can open in a browser (zoom, pan, hover):

```bash
python -m src.cli --player "Stephen Curry" --season "2023-24" --season_type "Regular Season" --metric fg_pct --interactive
```

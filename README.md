# NBA Shot Chart Visualizer (Real NBA.com Data)

## 📊 Preview

<div align="center">
  <img src="outputs/figures/screenshot.png" alt="NBA Shot Chart Preview" width="900">
</div>

This repo pulls **real** shot locations from the NBA.com Stats API (via `nba_api`) and renders a clean, professional half-court **hexbin** shot chart for either **frequency** or **efficiency (FG%)**.

### Demo Mode (no live data)
The app opens in **Demo mode**, which shows a bundled example chart when cache/network is unavailable.  
To fetch live NBA data locally:
1) Put headers in `.streamlit/secrets.toml` (see "Streamlit App" section).
2) Uncheck "Demo mode" in the sidebar.
3) Optionally pre-warm cache with:
   `python tools/refresh_cache.py --season "2023-24" --season_type "Regular Season" --force`

This prevents reviewers from seeing API throttling errors on shared/cloud networks while still demonstrating the full UI and visuals.

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

### Comparison Charts

Compare multiple players side-by-side with shared color scales:

```bash
python -m src.compare --players "Curry, LeBron, Durant" --season "2023-24" --metric fg_pct
```

### HTML Gallery

After generating interactive charts, build a gallery index:

```bash
python tools/build_html_index.py
```

Opens `outputs/html/index.html` in your browser to browse all generated charts.

### Cache Seeding

Seed cache from a CSV URL to avoid API rate limits:

```bash
python tools/seed_cache_from_url.py --player "Stephen Curry" --season "2023-24" --url "https://example.com/shots.csv" --force
streamlit run app.py  # Then use "Use cache only" mode
```

## Why this is real

- **Live NBA API pull**: Direct connection to NBA.com Stats API via `nba_api`
- **ShotChartDetail endpoint**: Uses official `ShotChartDetail` with `context_measure_simple="FGA"`
- **No CSV seeds**: All data fetched fresh from NBA.com, no pre-packaged datasets

## Reproducibility

```bash
git clone https://github.com/zaydabash/nba-shot-viz.git && cd nba-shot-viz
pip install -r requirements.txt
python src/cli.py --player "Stephen Curry" --season "2023-24"
```

## Roadmap

- **Team-level charts**: Visualize entire team shot patterns
- **League-relative efficiency**: Compare players against league averages
- **Shot zones**: Automatic zone detection and analysis
- **Streamlit web app**: Interactive web interface for non-technical users

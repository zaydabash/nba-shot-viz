from __future__ import annotations
import argparse
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List
from slugify import slugify
from .fetch_shots import fetch_and_cache
from .plot_shot_chart import plot_hexbin
from .court import draw_half_court


def compare_hexbin(players: List[str], season: str, season_type: str, metric: str = "fg_pct") -> str:
    """
    Generate a comparison hexbin chart with one subplot per player.
    Uses a shared color scale across all panels.
    """
    n_players = len(players)
    
    # Create subplots
    fig, axes = plt.subplots(1, n_players, figsize=(6.5 * n_players, 6.2), dpi=140)
    if n_players == 1:
        axes = [axes]  # Ensure axes is always a list
    
    # Collect all data to determine shared color scale
    all_data = []
    player_data = {}
    
    for player in players:
        csv_path = fetch_and_cache(player, season, season_type)
        df = pd.read_csv(csv_path)
        
        x = df["LOC_X"].to_numpy()
        y = df["LOC_Y"].to_numpy()
        made = df["SHOT_MADE_FLAG"].to_numpy()
        
        # Filter shots to offensive half only & sane bounds
        mask = (y >= 0) & (y <= 470) & (x >= -250) & (x <= 250)
        x_filtered = x[mask]
        y_filtered = y[mask]
        made_filtered = made[mask]
        
        player_data[player] = {
            'x': x_filtered,
            'y': y_filtered,
            'made': made_filtered
        }
        
        if metric == "fg_pct":
            all_data.extend(made_filtered)
        else:  # frequency
            all_data.extend(np.ones_like(made_filtered))
    
    # Determine shared color scale limits
    if metric == "fg_pct":
        vmin, vmax = 0, 1
    else:  # frequency
        vmin, vmax = 0, max(all_data) if all_data else 1
    
    # Generate subplots
    for i, player in enumerate(players):
        ax = axes[i]
        data = player_data[player]
        
        # Draw court
        draw_half_court(ax, line_color="#444", lw=1.4)
        
        if metric == "fg_pct":
            hb = ax.hexbin(data['x'], data['y'], C=data['made'], 
                          reduce_C_function=np.mean, gridsize=30,
                          extent=(-250, 250, 0, 470), mincnt=3, 
                          linewidths=0, vmin=vmin, vmax=vmax)
            cb_label = "FG% (per hex, min 3 att.)"
        else:  # frequency
            hb = ax.hexbin(data['x'], data['y'], gridsize=30,
                          extent=(-250, 250, 0, 470), mincnt=1,
                          linewidths=0, vmin=vmin, vmax=vmax)
            cb_label = "Attempts (count per hex)"
        
        # Add colorbar
        cb = plt.colorbar(hb, ax=ax, shrink=0.85, pad=0.01)
        cb.set_label(cb_label)
        
        # Set title
        ax.set_title(f"{player}", fontsize=12, fontweight="bold")
    
    # Overall title
    title = f"Shot Chart Comparison — {season} ({season_type})"
    subtitle = f"Metric: {metric.upper()} | NBA.com Stats via nba_api"
    fig.suptitle(title, y=0.96, fontsize=14, fontweight="bold")
    fig.text(0.5, 0.92, subtitle, ha='center', fontsize=10)
    
    # Save figure
    slug_season_type = slugify(season_type)
    out_path = f"outputs/figures/compare_{season.replace(' ', '_')}_{slug_season_type}_{metric}.png"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close()
    
    return out_path


def main():
    """CLI entry point for comparison charts."""
    parser = argparse.ArgumentParser(description="NBA Shot Chart Comparison Tool")
    parser.add_argument("--players", required=True, 
                       help='Comma-separated player names, e.g., "Curry, LeBron, Durant"')
    parser.add_argument("--season", required=True, help='e.g., "2023-24"')
    parser.add_argument("--season_type", default="Regular Season", 
                       choices=["Regular Season", "Playoffs", "Pre Season", "All Star"])
    parser.add_argument("--metric", default="fg_pct", choices=["fg_pct", "frequency"])
    
    args = parser.parse_args()
    
    # Parse player names
    players = [name.strip() for name in args.players.split(',')]
    
    print(f"Generating comparison chart for {len(players)} players: {', '.join(players)}")
    
    try:
        out_path = compare_hexbin(players, args.season, args.season_type, args.metric)
        print(f"Comparison chart saved → {out_path}")
    except Exception as e:
        print(f"Error generating comparison chart: {e}")


if __name__ == "__main__":
    main()

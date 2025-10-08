from __future__ import annotations
import argparse, os
import pandas as pd
from rich import print
from .fetch_shots import fetch_and_cache
from .plot_shot_chart import plot_hexbin, plot_plotly

def main():
    p = argparse.ArgumentParser(description="NBA Shot Chart Visualizer")
    p.add_argument("--player", required=True, help='e.g., "Stephen Curry" or "Stephen Curry, LeBron James"')
    p.add_argument("--season", required=True, help='e.g., "2023-24"')
    p.add_argument("--season_type", default="Regular Season", choices=["Regular Season","Playoffs","Pre Season","All Star"])
    p.add_argument("--metric", default="fg_pct", choices=["fg_pct","frequency"])
    p.add_argument("--gridsize", type=int, default=30)
    p.add_argument("--interactive", action='store_true', help='Generate interactive HTML chart')
    args = p.parse_args()

    # Parse comma-separated player names
    player_names = [name.strip() for name in args.player.split(',')]
    
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("outputs/figures", exist_ok=True)
    os.makedirs("outputs/html", exist_ok=True)
    
    print(f"[bold blue]Processing {len(player_names)} player(s): {', '.join(player_names)}[/bold blue]")
    print()
    
    for i, player in enumerate(player_names, 1):
        print(f"[bold yellow]Player {i}/{len(player_names)}: {player}[/bold yellow]")
        
        try:
            csv_path = fetch_and_cache(player, args.season, args.season_type)
            
            # Get shot count for summary
            df = pd.read_csv(csv_path)
            shot_count = len(df)
            
            out_png = plot_hexbin(csv_path, player, args.season, args.season_type,
                                  metric=args.metric, gridsize=args.gridsize)
            
            # Generate interactive HTML if requested
            out_html = None
            if args.interactive:
                out_html = plot_plotly(csv_path, player, args.season, args.season_type,
                                      metric=args.metric, bin_size=15)
            
            # Print per-player summary
            summary_parts = [f"[bold green]✓ {player}: {shot_count} shots", f"PNG: {out_png}"]
            if out_html:
                summary_parts.append(f"HTML: {out_html}")
            
            print(" | ".join(summary_parts))
        except Exception as e:
            print(f"[bold red]✗ Error processing {player}: {str(e)}[/bold red]")
        
        if i < len(player_names):
            print()  # Add spacing between players
    
    print()
    print(f"[bold cyan]Completed processing {len(player_names)} player(s)[/bold cyan]")

if __name__ == "__main__":
    main()

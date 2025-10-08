from __future__ import annotations
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
from typing import Literal, Optional
from slugify import slugify
from .court import draw_half_court

Metric = Literal["frequency","fg_pct"]

def _load(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "SHOT_MADE_FLAG" not in df.columns:
        raise ValueError("CSV missing SHOT_MADE_FLAG")
    return df

def plot_hexbin(csv_path: str, player: str, season: str, season_type: str, 
                metric: Metric="fg_pct", gridsize: int=30, save_png: bool=True) -> str:
    df = _load(csv_path)
    x = df["LOC_X"].to_numpy()
    y = df["LOC_Y"].to_numpy()
    made = df["SHOT_MADE_FLAG"].to_numpy()

    plt.figure(figsize=(6.5, 6.2), dpi=140)
    ax = plt.gca()
    draw_half_court(ax, line_color="#444", lw=1.4)

    if metric == "fg_pct":
        C = made
        reduce = np.mean
        hb = plt.hexbin(x, y, C=C, reduce_C_function=reduce, gridsize=gridsize,
                        extent=(-250,250,0,470), mincnt=3, linewidths=0)
        cb_label = "FG% (per hex, min 3 att.)"
    else:
        hb = plt.hexbin(x, y, gridsize=gridsize, extent=(-250,250,0,470),
                        mincnt=1, linewidths=0)
        cb_label = "Attempts (count per hex)"

    cb = plt.colorbar(hb, shrink=0.85, pad=0.01)
    cb.set_label(cb_label)

    title = f"{player} — {season} ({season_type})"
    subtitle = "Hexbin shot chart (NBA.com Stats via nba_api)"
    plt.suptitle(title, y=0.96, fontsize=12, fontweight="bold")
    plt.title(subtitle, fontsize=9)

    out = f"outputs/figures/{slugify(player)}_{season.replace(' ','_')}_{slugify(season_type)}_{metric}_hexbin.png"
    if save_png:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        plt.savefig(out, bbox_inches="tight", facecolor="white")
    return out

def plot_plotly(csv_path: str, player: str, season: str, season_type: str, metric: str = "fg_pct", bin_size: int = 15) -> str:
    """
    Create an interactive Plotly binned shot chart.
    """
    df = _load(csv_path)
    
    # Bin court coordinates into grid
    df['bin_x'] = ((df['LOC_X'] + 250) // bin_size).astype(int)
    df['bin_y'] = (df['LOC_Y'] // bin_size).astype(int)
    
    # Calculate bin centers
    df['bin_center_x'] = df['bin_x'] * bin_size - 250 + bin_size / 2
    df['bin_center_y'] = df['bin_y'] * bin_size + bin_size / 2
    
    # Group by bins and calculate metrics
    bin_stats = df.groupby(['bin_x', 'bin_y', 'bin_center_x', 'bin_center_y']).agg({
        'SHOT_MADE_FLAG': ['count', 'mean']
    }).reset_index()
    
    bin_stats.columns = ['bin_x', 'bin_y', 'bin_center_x', 'bin_center_y', 'attempts', 'fg_pct']
    
    # Filter based on metric
    if metric == "fg_pct":
        bin_stats = bin_stats[bin_stats['attempts'] >= 3]  # Hide bins with < 3 attempts
        color_col = 'fg_pct'
        color_title = 'FG%'
        colorscale = 'Viridis'
    else:  # frequency
        bin_stats = bin_stats[bin_stats['attempts'] >= 1]  # Show all bins with attempts
        color_col = 'attempts'
        color_title = 'Attempts'
        colorscale = 'Inferno'
    
    # Create scattergl plot
    fig = go.Figure()
    
    # Prepare customdata with NaN handling
    customdata = []
    for attempts, fg_pct in zip(bin_stats['attempts'], bin_stats['fg_pct']):
        fg_pct_val = fg_pct if not pd.isna(fg_pct) else None
        customdata.append([attempts, fg_pct_val])
    
    fig.add_trace(go.Scattergl(
        x=bin_stats['bin_center_x'],
        y=bin_stats['bin_center_y'],
        mode='markers',
        marker=dict(
            size=bin_stats['attempts'] * 2,  # Size proportional to attempts
            color=bin_stats[color_col],
            colorscale=colorscale,
            opacity=0.95,
            line=dict(width=0),
            showscale=True,
            colorbar=dict(title=color_title)
        ),
        hovertemplate=(
            "x: %{x:.0f}, y: %{y:.0f}<br>" +
            "Attempts: %{customdata[0]}<br>" +
            "FG%: %{customdata[1]:.2f}<extra></extra>"
        ),
        customdata=customdata
    ))
    
    # Add NBA court shapes (clean white lines for dark theme)
    court_shapes = [
        # Outer lines (half-court)
        dict(type="rect", x0=-250, y0=0, x1=250, y1=470, line=dict(color="#e6e6e6", width=1.2), fillcolor="rgba(0,0,0,0)"),
        
        # Lane/paint
        dict(type="rect", x0=-80, y0=0, x1=80, y1=190, line=dict(color="#e6e6e6", width=1.2), fillcolor="rgba(0,0,0,0)"),
        
        # Free-throw circle
        dict(type="circle", x0=-60, y0=130, x1=60, y1=250, line=dict(color="#e6e6e6", width=1.2), fillcolor="rgba(0,0,0,0)"),
        
        # Restricted area arc
        dict(type="path", path="M -40,60 A 40,40 0 0,1 40,60", line=dict(color="#e6e6e6", width=1.2), fillcolor="rgba(0,0,0,0)"),
        
        # Backboard
        dict(type="rect", x0=-30, y0=40, x1=30, y1=41, line=dict(color="#e6e6e6", width=1.2), fillcolor="#e6e6e6"),
        
        # Rim (small circle)
        dict(type="circle", x0=-7.5, y0=52.5, x1=7.5, y1=67.5, line=dict(color="#e6e6e6", width=1.2), fillcolor="rgba(0,0,0,0)"),
        
        # 3PT corners + arc
        dict(type="path", path="M -220,0 L -220,140 A 237.5,237.5 0 0,1 220,140 L 220,0", line=dict(color="#e6e6e6", width=1.2), fillcolor="rgba(0,0,0,0)"),
    ]
    
    fig.update_layout(
        template=None,
        paper_bgcolor="#0f1115",
        plot_bgcolor="#0f1115",
        font=dict(family="Inter, Helvetica, Arial, sans-serif", size=13, color="#e6e6e6"),
        margin=dict(l=20, r=20, t=70, b=20),
        width=980, height=720,
        title=dict(
            text=f"{player} — {season} ({season_type})",
            x=0.5, xanchor="center",
            font=dict(size=20, color="#ffffff")
        ),
        showlegend=False,
        xaxis=dict(
            range=[-250, 250],
            scaleanchor="y",
            scaleratio=1,
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            color="#e6e6e6"
        ),
        yaxis=dict(
            range=[470, 0],  # Inverted for TV-style view
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            color="#e6e6e6"
        ),
        shapes=court_shapes
    )
    
    # Save HTML with responsive configuration
    out_path = f"outputs/html/{slugify(player)}_{season.replace(' ','_')}_{slugify(season_type)}_{metric}.html"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.write_html(out_path, include_plotlyjs="cdn", full_html=True, config={"responsive": True})
    
    print(f"Interactive HTML chart saved → {out_path}")
    return out_path

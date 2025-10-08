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

def plot_plotly(csv_path: str, player: str, season: str, season_type: str) -> str:
    """
    Create an interactive Plotly scatter plot version of the shot chart.
    Saves to outputs/html/{player}_{season}.html
    """
    df = _load(csv_path)
    
    # Create scatter plot with different colors for made/missed shots
    fig = go.Figure()
    
    # Made shots
    made_shots = df[df["SHOT_MADE_FLAG"] == 1]
    fig.add_trace(go.Scatter(
        x=made_shots["LOC_X"],
        y=made_shots["LOC_Y"],
        mode='markers',
        marker=dict(
            size=8,
            color='green',
            opacity=0.7,
            line=dict(width=1, color='darkgreen')
        ),
        name='Made',
        hovertemplate='<b>Made Shot</b><br>' +
                      'Location: (%{x:.0f}, %{y:.0f})<br>' +
                      '<extra></extra>'
    ))
    
    # Missed shots
    missed_shots = df[df["SHOT_MADE_FLAG"] == 0]
    fig.add_trace(go.Scatter(
        x=missed_shots["LOC_X"],
        y=missed_shots["LOC_Y"],
        mode='markers',
        marker=dict(
            size=8,
            color='red',
            opacity=0.7,
            line=dict(width=1, color='darkred')
        ),
        name='Missed',
        hovertemplate='<b>Missed Shot</b><br>' +
                      'Location: (%{x:.0f}, %{y:.0f})<br>' +
                      '<extra></extra>'
    ))
    
    # Add court outline (simplified)
    court_shapes = [
        # Hoop
        dict(type="circle", x0=-7.5, y0=52.5, x1=7.5, y1=67.5, line=dict(color="black", width=2)),
        # Backboard
        dict(type="rect", x0=-30, y0=40, x1=30, y1=41, line=dict(color="black", width=2)),
        # Paint
        dict(type="rect", x0=-80, y0=0, x1=80, y1=190, line=dict(color="black", width=2)),
        # Free throw line
        dict(type="rect", x0=-60, y0=0, x1=60, y1=190, line=dict(color="black", width=2)),
        # Three-point line (simplified arc)
        dict(type="path", path="M -220,0 L -220,140 A 237.5,237.5 0 0,1 220,140 L 220,0", line=dict(color="black", width=2)),
        # Court boundaries
        dict(type="rect", x0=-250, y0=0, x1=250, y1=470, line=dict(color="black", width=2), fillcolor="rgba(0,0,0,0)")
    ]
    
    fig.update_layout(
        title=f"{player} — {season} ({season_type})<br><sub>Interactive Shot Chart (NBA.com Stats via nba_api)</sub>",
        xaxis=dict(
            range=[-250, 250],
            scaleanchor="y",
            scaleratio=1,
            showgrid=False,
            zeroline=False,
            showticklabels=False
        ),
        yaxis=dict(
            range=[470, 0],  # Inverted for TV-style view
            showgrid=False,
            zeroline=False,
            showticklabels=False
        ),
        shapes=court_shapes,
        plot_bgcolor='white',
        width=800,
        height=600,
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        )
    )
    
    # Save to HTML
    out_path = f"outputs/html/{slugify(player)}_{season.replace(' ','_')}.html"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.write_html(out_path)
    
    return out_path

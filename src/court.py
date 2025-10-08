from __future__ import annotations
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Arc

COURT_X_MIN, COURT_X_MAX = -250, 250
COURT_Y_MIN, COURT_Y_MAX = 0, 470

def draw_half_court(ax=None, line_color="#222", lw=1.5):
    if ax is None:
        ax = plt.gca()

    # Hoop, backboard
    hoop = Circle((0, 60), radius=7.5, linewidth=lw, color=line_color, fill=False)
    backboard = Rectangle((-30, 40), 60, 1, linewidth=lw, color=line_color, fill=True)

    # Paint
    paint = Rectangle((-80, 0), 160, 190, linewidth=lw, color=line_color, fill=False)
    inner_box = Rectangle((-60, 0), 120, 190, linewidth=lw, color=line_color, fill=False)

    # Free throw
    ft_circle = Circle((0, 190), radius=60, linewidth=lw, color=line_color, fill=False)

    # Restricted area
    ra_arc = Arc((0, 60), 80, 80, theta1=0, theta2=180, linewidth=lw, color=line_color)

    # Three-point line
    corner_left = Rectangle(( -220, 0), 0.01, 140, linewidth=lw, color=line_color, fill=True)
    corner_right= Rectangle((  220, 0), 0.01, 140, linewidth=lw, color=line_color, fill=True)
    arc3 = Arc((0, 60), 475, 475, theta1=22, theta2=158, linewidth=lw, color=line_color)

    # Outer lines (half court only)
    outer = Rectangle((COURT_X_MIN, -47.5), 500, 470, linewidth=lw, color=line_color, fill=False)

    elems = [hoop, backboard, paint, inner_box, ft_circle, ra_arc, corner_left, corner_right, arc3, outer]
    for e in elems:
        ax.add_patch(e)

    ax.set_xlim(COURT_X_MIN, COURT_X_MAX)
    ax.set_ylim(COURT_Y_MAX, COURT_Y_MIN)  # invert y for TV-style top-down look
    ax.axis("off")
    return ax

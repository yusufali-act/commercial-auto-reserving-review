"""Consistent chart styling for the project.

Colours are assigned to an *entity* (a method or a data basis) once, here, so
the same method is the same colour in every chart. Palette: a validated,
colour-blind-checked categorical order (blue, orange, aqua, yellow, magenta,
green, violet, red).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .data import ROOT

FIG_DIR = ROOT / "outputs" / "figures"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
NEUTRAL = "#8a8985"

COLOURS = {
    # data bases
    "paid": SERIES[0],
    "case": SERIES[1],
    "incurred": SERIES[1],
    # methods (paid-based in blue family position, case-based in orange position etc.)
    "CL paid": SERIES[0],
    "CL case": SERIES[1],
    "Cape Cod case": SERIES[2],
    "BF case": SERIES[3],
    "Cape Cod paid": SERIES[4],
    "Benktander case": SERIES[5],
    "Gen. Cape Cod case": SERIES[6],
    "BF paid": SERIES[7],
    "ELR": NEUTRAL,
    "Selected": INK,
    "Blended": INK,
    "Actual": NEUTRAL,
    "True": NEUTRAL,
}


def setup() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK_2,
            "axes.titlecolor": INK,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.titlepad": 20,
            "axes.labelsize": 10,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "xtick.color": INK_2,
            "ytick.color": INK_2,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "lines.linewidth": 2,
            "lines.markersize": 6,
            "font.family": "sans-serif",
            "figure.dpi": 110,
            "savefig.dpi": 160,
            "savefig.bbox": "tight",
        }
    )


def save(fig, name: str) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    p = FIG_DIR / f"{name}.png"
    fig.savefig(p)
    return p


def subtitle(ax, text: str) -> None:
    ax.text(0, 1.015, text, transform=ax.transAxes, fontsize=9, color=INK_2, va="bottom")


def money(ax, axis: str = "y", unit: str = "m", scale: float = 1.0, prefix: str = "") -> None:
    fmt = mpl.ticker.FuncFormatter(lambda v, _: f"{prefix}{v / scale:,.0f}{unit}")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def pct(ax, axis: str = "y", decimals: int = 0) -> None:
    fmt = mpl.ticker.PercentFormatter(1.0, decimals=decimals)
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


# --------------------------------------------------------------------------- #
# Reusable charts
# --------------------------------------------------------------------------- #
def link_ratio_heatmap(lr: pd.DataFrame, flags: pd.DataFrame | None = None, title: str = "", ax=None):
    """Link ratios shaded by deviation from the column median (diverging, grey midpoint)."""
    ax = ax or plt.subplots(figsize=(9, 4.8))[1]
    dev = lr / lr.median() - 1
    lim = np.nanpercentile(np.abs(dev.values), 95) or 0.01
    cmap = mpl.colors.LinearSegmentedColormap.from_list("div", ["#2a78d6", "#f0efec", "#e34948"])
    ax.imshow(dev.values, cmap=cmap, vmin=-lim, vmax=lim, aspect="auto")
    ax.grid(False)
    for i in range(lr.shape[0]):
        for j in range(lr.shape[1]):
            v = lr.iat[i, j]
            if np.isnan(v):
                continue
            flagged = flags is not None and bool(flags.iat[i, j])
            ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=8,
                    color=INK, fontweight="bold" if flagged else "normal")
            if flagged:
                ax.add_patch(mpl.patches.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, ec=INK, lw=1.5))
    ax.set_xticks(range(lr.shape[1]), [f"{a}-{a + 1}" for a in lr.columns])
    ax.set_yticks(range(lr.shape[0]), lr.index)
    ax.set_xlabel("Development age (years)")
    ax.set_title(title)
    return ax


def method_dots(unpaid: pd.DataFrame, actual: pd.Series | None = None, title: str = "", scale: float = 1e3, unit: str = "m", ax=None):
    """Dot plot of unpaid by origin for several methods (one row per origin)."""
    ax = ax or plt.subplots(figsize=(9, 5.5))[1]
    origins = list(unpaid.index)
    y = np.arange(len(origins))
    k = len(unpaid.columns)
    offsets = np.linspace(-0.25, 0.25, k) if k > 1 else [0]
    for off, m in zip(offsets, unpaid.columns):
        ax.scatter(unpaid[m] / scale, y + off, s=34, color=COLOURS.get(m, NEUTRAL), label=m, zorder=3,
                   edgecolor=SURFACE, linewidth=1)
    if actual is not None:
        ax.scatter(actual / scale, y, marker="|", s=260, color=INK, label="Actual (hindsight)", zorder=4, linewidth=2)
    ax.set_yticks(y, origins)
    ax.invert_yaxis()
    ax.grid(True, axis="x")
    ax.grid(False, axis="y")
    ax.set_xlabel(f"Unpaid ({unit})")
    ax.legend(loc="lower right")
    ax.set_title(title)
    return ax

"""
Figures for external write-ups, generated from the model rather than drawn.

A chart in a portfolio that was exported once and then edited by hand is a
claim nobody can re-derive. These are produced from backtest.run_all(), so a
fact correction moves the picture and a stale figure is a build step away from
being caught rather than a thing someone has to remember.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src import backtest

METRICS = [("revenue", "Revenue"),
           ("operating_profit", "Operating profit"),
           ("free_cash_flow", "Free cash flow")]

NAIVE = "#e8622a"
DRIVEN = "#2b7bd6"
INK = "#1f2421"
MUTED = "#5b6560"
GROUND = "#faf9f7"


def forecast_error(out: Path) -> Path:
    """Absolute forecast error by metric, both vintages, driver-based vs naive.

    Shared x-axis on purpose: the FY2024 miss is several times the FY2025 one,
    and rescaling each panel to fill its own width would hide exactly that.
    """
    runs = backtest.run_all()
    widest = max(abs(r[m][f"{k}_error_pct"])
                 for r in runs for m in ("naive", "driver_based") for k, _ in METRICS)

    fig, axes = plt.subplots(len(runs), 1, figsize=(11.5, 7.6), sharex=True)
    fig.patch.set_facecolor(GROUND)

    for ax, run in zip(axes, runs):
        ax.set_facecolor(GROUND)
        positions = range(len(METRICS))
        for offset, (series, colour, label) in enumerate(
            [("naive", NAIVE, "Naive extrapolation"),
             ("driver_based", DRIVEN, "Driver-based (guidance-informed)")]
        ):
            values = [abs(run[series][f"{k}_error_pct"]) for k, _ in METRICS]
            bars = ax.barh([p + offset * 0.4 for p in positions], values,
                           height=0.38, color=colour, label=label, zorder=3)
            for bar, value in zip(bars, values):
                ax.text(value + widest * 0.012, bar.get_y() + bar.get_height() / 2,
                        f"{value:.1f}%", va="center", fontsize=10, color=INK)

        ax.set_yticks([p + 0.2 for p in positions])
        ax.set_yticklabels([label for _, label in METRICS], fontsize=11, color=INK)
        ax.invert_yaxis()
        ax.set_title(f"{run['label']}   ·   guidance published {run['guidance_published']}",
                     fontsize=12, color=INK, loc="left", pad=10)
        ax.grid(axis="x", color="#d9d6d0", linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color("#c9c5be")
        ax.tick_params(colors=MUTED)
        ax.set_xlim(0, widest * 1.16)

    axes[0].legend(loc="lower right", frameon=False, fontsize=10.5)
    axes[-1].set_xlabel("Absolute forecast error vs. actuals (%)", fontsize=10.5, color=MUTED)

    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor=GROUND)
    plt.close(fig)
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/forecast-error.png")
    print(f"Wrote {forecast_error(target)}")

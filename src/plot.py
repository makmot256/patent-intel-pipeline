"""Publication-quality matplotlib charts saved to reports/charts/.

Produces five PNG files by default:
    trend.png             - patents granted per year (line)
    top_countries.png     - top 15 countries (horizontal bar)
    top_companies.png     - top 10 companies (horizontal bar)
    top_inventors.png     - top 10 inventors (horizontal bar)
    cpc_sections.png      - CPC section share (donut, only if CPC loaded)
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from src.analyze import run_all
from src.config import BRAND, CHARTS_DIR, PALETTE


# ----------------------------------------------------------------------
# Shared styling
# ----------------------------------------------------------------------
plt.rcParams.update({
    "font.family":         "DejaVu Sans",
    "axes.titlesize":      15,
    "axes.titleweight":    "bold",
    "axes.titlepad":       28,
    "axes.labelsize":      11,
    "axes.edgecolor":      "#E5E7EB",
    "axes.linewidth":      1.0,
    "axes.grid":           True,
    "grid.color":          "#F3F4F6",
    "grid.linewidth":      0.8,
    "xtick.color":         BRAND["muted"],
    "ytick.color":         BRAND["muted"],
    "legend.frameon":      False,
    "figure.facecolor":    "white",
    "savefig.dpi":         150,
    "savefig.bbox":        "tight",
})


def _style_axes(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color("#E5E7EB")
    ax.spines["bottom"].set_color("#E5E7EB")


def _title(ax, title: str, subtitle: str | None = None) -> None:
    # Use figure-relative annotations so title + subtitle never collide
    # with the plotting area regardless of figure size.
    fig = ax.figure
    fig.text(0.02, 0.96, title, fontsize=16, fontweight="bold",
             color=BRAND["dark"], ha="left", va="top")
    if subtitle:
        fig.text(0.02, 0.915, subtitle, fontsize=10,
                 color=BRAND["muted"], ha="left", va="top")


# ----------------------------------------------------------------------
# Individual charts
# ----------------------------------------------------------------------
def plot_trend(df: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9, 5))
    fig.subplots_adjust(top=0.82)
    ax.plot(df["year"], df["patent_count"],
            marker="o", linewidth=3, color=BRAND["primary"],
            markersize=9, markerfacecolor="white",
            markeredgewidth=2.5, markeredgecolor=BRAND["primary"])
    ax.fill_between(df["year"], df["patent_count"], alpha=0.10, color=BRAND["primary"])

    for x, y in zip(df["year"], df["patent_count"]):
        ax.annotate(f"{y:,}", xy=(x, y), xytext=(0, 12),
                    textcoords="offset points", ha="center",
                    fontsize=9, color=BRAND["dark"], fontweight="bold")

    ax.set_xlabel("Year")
    ax.set_ylabel("Patents granted")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.set_xticks(df["year"])
    _style_axes(ax)
    _title(ax, "Patents granted per year",
           "Q4 | USPTO granted patents, filtered subset")

    out = CHARTS_DIR / "trend.png"
    fig.savefig(out)
    plt.close(fig)
    return str(out)


def _hbar(df: pd.DataFrame, label_col: str, value_col: str,
          title: str, subtitle: str, filename: str, color: str) -> str:
    df = df.sort_values(value_col).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9, max(4.5, 0.48 * len(df) + 1.4)))
    fig.subplots_adjust(top=0.86)
    bars = ax.barh(df[label_col].astype(str), df[value_col],
                   color=color, edgecolor="white", linewidth=1.2)
    xmax = df[value_col].max()
    for bar, v in zip(bars, df[value_col]):
        ax.text(bar.get_width() + xmax * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{int(v):,}", va="center", fontsize=9,
                color=BRAND["dark"], fontweight="bold")
    ax.set_xlabel("Patents")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, xmax * 1.15)
    _style_axes(ax)
    _title(ax, title, subtitle)

    out = CHARTS_DIR / filename
    fig.savefig(out)
    plt.close(fig)
    return str(out)


def plot_top_countries(df: pd.DataFrame) -> str:
    return _hbar(df.head(15), "country", "patent_count",
                 "Top countries by patent volume",
                 "Q3 | inventor-country attribution",
                 "top_countries.png", BRAND["primary"])


def plot_top_companies(df: pd.DataFrame) -> str:
    return _hbar(df.head(10), "company", "patent_count",
                 "Top companies by patent volume",
                 "Q2 | disambiguated assignees",
                 "top_companies.png", BRAND["accent"])


def plot_top_inventors(df: pd.DataFrame) -> str:
    return _hbar(df.head(10), "inventor", "patent_count",
                 "Top inventors by patent volume",
                 "Q1 | disambiguated inventors",
                 "top_inventors.png", "#8B5CF6")


def plot_cpc_sections(df: pd.DataFrame) -> str | None:
    if df is None or df.empty:
        return None
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.subplots_adjust(top=0.88)
    labels = [f"{r.section_code} {r.description}" for r in df.itertuples()]
    values = df["patent_count"].to_numpy()
    colors = PALETTE[: len(values)]
    wedges, _ = ax.pie(values, startangle=140, colors=colors,
                       wedgeprops=dict(width=0.38, edgecolor="white", linewidth=3))
    ax.set_aspect("equal")
    total = int(values.sum())
    ax.text(0, 0.1, f"{total:,}", ha="center", va="center",
            fontsize=22, fontweight="bold", color=BRAND["dark"])
    ax.text(0, -0.12, "patents classified", ha="center", va="center",
            fontsize=10, color=BRAND["muted"])
    ax.legend(wedges, labels, loc="center left",
              bbox_to_anchor=(1.02, 0.5), frameon=False, fontsize=9)
    _title(ax, "CPC innovation-category mix",
           "Q8 | share of patents by top-level CPC section")

    out = CHARTS_DIR / "cpc_sections.png"
    fig.savefig(out)
    plt.close(fig)
    return str(out)


# ----------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------
def main() -> None:
    results = run_all()
    produced: list[str] = []
    produced.append(plot_trend(results["Q4"]))
    produced.append(plot_top_countries(results["Q3"]))
    produced.append(plot_top_companies(results["Q2"]))
    produced.append(plot_top_inventors(results["Q1"]))

    cpc = results.get("Q8")
    cpc_out = plot_cpc_sections(cpc if cpc is not None else pd.DataFrame())
    if cpc_out:
        produced.append(cpc_out)

    print("\nCharts written:")
    for p in produced:
        print(f"  * {p}")


if __name__ == "__main__":
    main()

"""Chart generation utilities — returns base64-encoded PNG strings."""

from __future__ import annotations

import base64
import io
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# ── Colour helpers ─────────────────────────────────────────────────────────

def cohort_palette(n: int) -> list[str]:
    """Return n cohort colours using seaborn cubehelix palette."""
    import seaborn as sns
    return [f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            for r, g, b in sns.color_palette("cubehelix", n)]


# ── NPV charts ─────────────────────────────────────────────────────────────

def npv_line_chart(
    data: dict[str, dict[int, float]],   # {type_label: {band: value}}
    title: str = "NPV by Aki Band",
    colors: Optional[dict[str, str]] = None,
    brand_color: str = "#820AD1",
) -> str:
    """Grouped line chart with one series per model type. Returns base64 PNG."""
    default_colors = {
        list(data.keys())[0]: brand_color,
        list(data.keys())[1] if len(data) > 1 else "__": "#3B82F6",
        list(data.keys())[2] if len(data) > 2 else "__": "#F59E0B",
        list(data.keys())[3] if len(data) > 3 else "__": "#6B7280",
    }
    colors = {**default_colors, **(colors or {})}

    markers = ["o", "s", "^", "D", "v", "P"]
    bands = sorted({b for series in data.values() for b in series})

    fig, ax = plt.subplots(figsize=(13, 6))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#fafafa")

    for i, (label, series) in enumerate(data.items()):
        vals = [series.get(b) for b in bands]
        ax.plot(bands, vals, color=colors.get(label, "#333"),
                marker=markers[i % len(markers)], linewidth=2.2, markersize=6,
                label=label, zorder=3)

    ax.axhline(0, color="#374151", linewidth=0.8, linestyle="--", alpha=0.5, zorder=2)
    ax.yaxis.grid(True, color="#e5e7eb", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xticks(bands)
    ax.set_xticklabels([f"Aki {b}" for b in bands], fontsize=10, color="#374151")
    ax.set_ylabel("NPV with Mgm (USD)", fontsize=11, color="#374151")
    ax.set_title(title, fontsize=13, fontweight="bold", color="#111827", pad=12)
    ax.tick_params(colors="#6b7280", labelsize=10)
    for spine in ax.spines.values():
        spine.set_edgecolor("#e5e7eb")
    ax.legend(fontsize=10, framealpha=0.9, edgecolor="#e5e7eb", facecolor="white")
    plt.tight_layout(pad=1.5)
    return _fig_to_b64(fig)


def npv_bar_chart(
    data: dict[str, dict[int, float]],
    title: str = "NPV by Aki Band",
    colors: Optional[dict[str, str]] = None,
    brand_color: str = "#820AD1",
) -> str:
    """Grouped bar chart with one bar group per aki band. Returns base64 PNG."""
    default_colors = {
        list(data.keys())[0]: brand_color,
        list(data.keys())[1] if len(data) > 1 else "__": "#3B82F6",
        list(data.keys())[2] if len(data) > 2 else "__": "#F59E0B",
        list(data.keys())[3] if len(data) > 3 else "__": "#6B7280",
    }
    colors = {**default_colors, **(colors or {})}

    types = list(data.keys())
    bands = sorted({b for series in data.values() for b in series})
    x = np.arange(len(bands))
    width = 0.18
    offsets = np.linspace(-(len(types) - 1) / 2 * width, (len(types) - 1) / 2 * width, len(types))

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#fafafa")

    for i, t in enumerate(types):
        vals = [data[t].get(b, 0) for b in bands]
        ax.bar(x + offsets[i], vals, width, color=colors.get(t, "#333"), label=t,
               zorder=3, edgecolor="white", linewidth=0.5)

    ax.axhline(0, color="#374151", linewidth=0.8, zorder=2)
    ax.yaxis.grid(True, color="#e5e7eb", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xticks(x)
    ax.set_xticklabels([f"Aki {b}" for b in bands], fontsize=10, color="#374151")
    ax.set_ylabel("NPV with Mgm (USD)", fontsize=11, color="#374151")
    ax.set_title(title, fontsize=13, fontweight="bold", color="#111827", pad=12)
    ax.tick_params(colors="#6b7280", labelsize=10)
    for spine in ax.spines.values():
        spine.set_edgecolor("#e5e7eb")
    ax.legend(fontsize=10, framealpha=0.9, edgecolor="#e5e7eb", facecolor="white")
    plt.tight_layout(pad=1.5)
    return _fig_to_b64(fig)


# ── Cohort monitoring chart ────────────────────────────────────────────────

def cohort_monitoring_chart(
    df,                             # pandas DataFrame with cohort monitoring data
    metric: str,
    aki_bands: list[int],
    legend_map: dict[str, str],     # e.g. {"static": "actuals", "running": "pClip"}
    max_month: int = 18,
    brand_color: str = "#820AD1",
) -> str:
    """
    3-row × ceil(n_bands/3)-col grid of line charts, one panel per aki band.
    Static/running lines styled with dashed/dotted black/gray.
    Cohort lines coloured with cubehelix palette.
    Returns base64 PNG.
    """
    import math, pandas as pd

    df = df.copy()
    df["month"] = pd.to_numeric(df["month"], errors="coerce")
    df[metric] = pd.to_numeric(df[metric], errors="coerce")

    # Build business_calendar_month from cohort + month
    def _bcm(row):
        cohort = str(row["cohort"])
        try:
            if "Q" in cohort:
                year, q = cohort.split("Q")
                start_month = (int(q) - 1) * 3 + 1
            else:
                year, m_part = cohort[:4], cohort[4:]
                start_month = int(m_part) if m_part.isdigit() else 1
            return int(year) * 12 + start_month - 1 + int(row["month"])
        except Exception:
            return None

    df["bcm"] = df.apply(_bcm, axis=1)

    cohorts = sorted(df[df["cohort"].astype(str).str.match(r"^\d{4}Q?\d")]["cohort"].unique())
    palette = cohort_palette(max(len(cohorts), 1))
    cohort_color = {c: palette[i] for i, c in enumerate(cohorts)}

    static_styles  = {"color": "black",  "linestyle": "--", "linewidth": 1.5, "alpha": 0.9}
    running_styles = {"color": "gray",   "linestyle": ":", "linewidth": 1.5, "alpha": 0.9}

    n_bands = len(aki_bands)
    n_cols = min(3, n_bands)
    n_rows = math.ceil(n_bands / n_cols)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(7 * n_cols, 4.5 * n_rows),
                             squeeze=False)
    fig.patch.set_facecolor("#ffffff")

    for idx, band in enumerate(sorted(aki_bands)):
        row, col = divmod(idx, n_cols)
        ax = axes[row][col]
        band_df = df[(df["aki_band"].astype(str) == str(band)) &
                     (df["month"].between(0, max_month))]

        for cohort, cdf in band_df[band_df["cohort"].astype(str).str.match(r"^\d{4}Q?\d")].groupby("cohort"):
            cdf = cdf.sort_values("month")
            ax.plot(cdf["month"], cdf[metric], color=cohort_color.get(cohort, "#888"),
                    linewidth=1.2, alpha=0.85)

        # Static / running overlay
        for overlay, styles in [("static", static_styles), ("running", running_styles)]:
            odf = band_df[band_df["cohort"].astype(str) == overlay].sort_values("month")
            if not odf.empty:
                label = legend_map.get(overlay, overlay)
                ax.plot(odf["month"], odf[metric], **styles, label=label)

        ax.set_title(f"Aki {band}", fontsize=10, fontweight="600", color="#374151")
        ax.yaxis.grid(True, color="#e5e7eb", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(labelsize=8, colors="#6b7280")
        for spine in ax.spines.values():
            spine.set_edgecolor("#e5e7eb")

    # Hide unused subplots
    for idx in range(n_bands, n_rows * n_cols):
        r, c = divmod(idx, n_cols)
        axes[r][c].set_visible(False)

    # Single legend for overlays
    handles = [
        plt.Line2D([0], [0], **{**static_styles,  "label": legend_map.get("static",  "actuals")}),
        plt.Line2D([0], [0], **{**running_styles, "label": legend_map.get("running", "pClip")}),
    ]
    fig.legend(handles=handles, loc="upper right", fontsize=9, framealpha=0.9)
    plt.tight_layout(pad=1.2)
    return _fig_to_b64(fig)


# ── Helpers ─────────────────────────────────────────────────────────────────

def image_to_b64(path: str) -> str:
    """Read any image file and return base64 string."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _fig_to_b64(fig: plt.Figure, dpi: int = 150) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return b64

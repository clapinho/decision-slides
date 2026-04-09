"""Chart generation utilities — returns base64-encoded PNG strings."""

from __future__ import annotations

import base64
import io
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


# ── Colour helpers ─────────────────────────────────────────────────────────

def cohort_palette(n: int) -> list[str]:
    """Return n cohort colours using seaborn cubehelix palette."""
    import seaborn as sns
    return [f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            for r, g, b in sns.color_palette("cubehelix", n)]


# ── NPV charts ─────────────────────────────────────────────────────────────

def npv_line_chart(
    data: dict[str, dict[int, float]],   # {series_label: {band: value}}
    title: str = "NPV by Risk Band",
    y_label: str = "NPV",
    band_label: str = "Band",
    colors: Optional[dict[str, str]] = None,
    brand_color: str = "#7c3aed",
) -> str:
    """Grouped line chart with one series per model type. Returns base64 PNG."""
    keys = list(data.keys())
    default_colors = {
        keys[0] if len(keys) > 0 else "__": brand_color,
        keys[1] if len(keys) > 1 else "__": "#3B82F6",
        keys[2] if len(keys) > 2 else "__": "#F59E0B",
        keys[3] if len(keys) > 3 else "__": "#6B7280",
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
    ax.set_xticklabels([f"{band_label} {b}" for b in bands], fontsize=10, color="#374151")
    ax.set_ylabel(y_label, fontsize=11, color="#374151")
    ax.set_title(title, fontsize=13, fontweight="bold", color="#111827", pad=12)
    ax.tick_params(colors="#6b7280", labelsize=10)
    for spine in ax.spines.values():
        spine.set_edgecolor("#e5e7eb")
    ax.legend(fontsize=10, framealpha=0.9, edgecolor="#e5e7eb", facecolor="white")
    plt.tight_layout(pad=1.5)
    return _fig_to_b64(fig)


def npv_bar_chart(
    data: dict[str, dict[int, float]],
    title: str = "NPV by Risk Band",
    y_label: str = "NPV",
    band_label: str = "Band",
    colors: Optional[dict[str, str]] = None,
    brand_color: str = "#7c3aed",
) -> str:
    """Grouped bar chart with one bar group per risk band. Returns base64 PNG."""
    keys = list(data.keys())
    default_colors = {
        keys[0] if len(keys) > 0 else "__": brand_color,
        keys[1] if len(keys) > 1 else "__": "#3B82F6",
        keys[2] if len(keys) > 2 else "__": "#F59E0B",
        keys[3] if len(keys) > 3 else "__": "#6B7280",
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
    ax.set_xticklabels([f"{band_label} {b}" for b in bands], fontsize=10, color="#374151")
    ax.set_ylabel(y_label, fontsize=11, color="#374151")
    ax.set_title(title, fontsize=13, fontweight="bold", color="#111827", pad=12)
    ax.tick_params(colors="#6b7280", labelsize=10)
    for spine in ax.spines.values():
        spine.set_edgecolor("#e5e7eb")
    ax.legend(fontsize=10, framealpha=0.9, edgecolor="#e5e7eb", facecolor="white")
    plt.tight_layout(pad=1.5)
    return _fig_to_b64(fig)


# ── Cohort monitoring chart ────────────────────────────────────────────────

def cohort_monitoring_chart(
    df,
    metric: str,
    risk_bands: list[int],
    band_column: str = "risk_band",
    legend_map: Optional[dict[str, str]] = None,
    overlay_keys: Optional[list[str]] = None,  # non-cohort rows (e.g. baselines)
    max_month: int = 18,
    brand_color: str = "#7c3aed",
) -> str:
    """
    Grid of line charts — one panel per risk band value.
    Cohort rows are coloured with a cubehelix palette.
    Overlay rows (e.g. "baseline", "challenger") are styled with dashed/dotted lines.
    Returns base64 PNG.

    Args:
        df: DataFrame with columns [band_column, cohort, month, metric, ...]
        metric: metric column name to plot
        risk_bands: list of band values to include
        band_column: DataFrame column name for the band identifier
        legend_map: rename overlay cohort labels {original: display_name}
        overlay_keys: cohort values that are overlays (not individual cohorts);
                      detected automatically if None (non-numeric cohort values)
        max_month: x-axis upper limit
    """
    import math
    import pandas as pd

    legend_map = legend_map or {}
    df = df.copy()
    df["month"] = pd.to_numeric(df["month"], errors="coerce")
    df[metric] = pd.to_numeric(df[metric], errors="coerce")

    # Detect cohort rows: anything that looks like YYYY or YYYYQn
    cohort_mask = df["cohort"].astype(str).str.match(r"^\d{4}Q?\d")
    cohorts = sorted(df[cohort_mask]["cohort"].unique())
    palette = cohort_palette(max(len(cohorts), 1))
    cohort_color = {c: palette[i] for i, c in enumerate(cohorts)}

    # Overlay rows: anything not a dated cohort
    if overlay_keys is None:
        overlay_keys = sorted(df[~cohort_mask]["cohort"].astype(str).unique())

    overlay_linestyles = ["--", ":", "-.", (0, (3, 1, 1, 1))]
    overlay_colors = ["black", "#555", "#888", "#bbb"]
    overlay_styles = {
        key: {
            "color": overlay_colors[i % len(overlay_colors)],
            "linestyle": overlay_linestyles[i % len(overlay_linestyles)],
            "linewidth": 1.5,
            "alpha": 0.9,
        }
        for i, key in enumerate(overlay_keys)
    }

    n_bands = len(risk_bands)
    n_cols = min(3, max(n_bands, 1))
    n_rows = math.ceil(n_bands / n_cols)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(7 * n_cols, 4.5 * n_rows),
                             squeeze=False)
    fig.patch.set_facecolor("#ffffff")

    for idx, band in enumerate(sorted(risk_bands)):
        r, c = divmod(idx, n_cols)
        ax = axes[r][c]
        band_df = df[
            (df[band_column].astype(str) == str(band)) &
            (df["month"].between(0, max_month))
        ]

        # Cohort lines
        for cohort, cdf in band_df[cohort_mask.reindex(band_df.index, fill_value=False)].groupby("cohort"):
            cdf = cdf.sort_values("month")
            ax.plot(cdf["month"], cdf[metric],
                    color=cohort_color.get(cohort, "#888"),
                    linewidth=1.2, alpha=0.85)

        # Overlay lines
        for key, styles in overlay_styles.items():
            odf = band_df[band_df["cohort"].astype(str) == key].sort_values("month")
            if not odf.empty:
                label = legend_map.get(key, key)
                ax.plot(odf["month"], odf[metric], **styles, label=label)

        ax.set_title(f"Band {band}", fontsize=10, fontweight="600", color="#374151")
        ax.yaxis.grid(True, color="#e5e7eb", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(labelsize=8, colors="#6b7280")
        for spine in ax.spines.values():
            spine.set_edgecolor("#e5e7eb")

    # Hide unused subplots
    for idx in range(n_bands, n_rows * n_cols):
        r2, c2 = divmod(idx, n_cols)
        axes[r2][c2].set_visible(False)

    # Legend for overlay lines
    if overlay_keys:
        handles = [
            plt.Line2D([0], [0], **{**overlay_styles[k], "label": legend_map.get(k, k)})
            for k in overlay_keys
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

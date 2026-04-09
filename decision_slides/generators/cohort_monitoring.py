"""Cohort monitoring slides — one slide per metric."""

from __future__ import annotations

from ..config import CohortMonitoringConfig
from ..charts import cohort_monitoring_chart
from .base import image_slide, BRAND_PURPLE


def fetch_data(client, cfg: CohortMonitoringConfig):
    """Fetch cohort monitoring data from the configured table."""
    import pandas as pd

    band_filter = ""
    if cfg.risk_bands:
        bands_str = ",".join(str(b) for b in cfg.risk_bands)
        band_filter = f"AND {cfg.band_column} IN ({bands_str})"

    month_filter = f"AND month <= {cfg.max_month}" if cfg.max_month else ""

    metric_cols = ", ".join(cfg.metrics) if cfg.metrics else "*"
    sql = f"""
        SELECT {cfg.band_column}, cohort, month, {metric_cols}
        FROM {cfg.table}
        WHERE 1=1
          {band_filter}
          {month_filter}
        ORDER BY {cfg.band_column}, cohort, month
    """
    rows = client.query(sql)
    df = pd.DataFrame(rows)
    # Rename band column to expected name for chart function
    if cfg.band_column != "risk_band" and cfg.band_column in df.columns:
        df = df.rename(columns={cfg.band_column: "risk_band"})
    return df


def _metric_display_name(metric: str) -> str:
    """Convert a snake_case column name to a readable title."""
    return metric.replace("_", " ").title()


def generate_all(
    df,
    cfg: CohortMonitoringConfig,
    brand_color: str = BRAND_PURPLE,
    start_index: int = 1,
) -> list[tuple[str, str]]:
    """
    Generate one slide per metric.
    If cfg.metrics is empty, all numeric columns (excluding band/cohort/month) are used.
    Returns list of (filename, html) pairs.
    """
    import pandas as pd

    if cfg.metrics:
        metrics = cfg.metrics
    else:
        exclude = {"risk_band", cfg.band_column, "cohort", "month"}
        metrics = [c for c in df.columns if c not in exclude
                   and pd.api.types.is_numeric_dtype(df[c])]

    risk_bands = cfg.risk_bands or sorted(df["risk_band"].unique().tolist()
                                          if "risk_band" in df.columns else [])

    slides = []
    for i, metric in enumerate(metrics):
        if metric not in df.columns:
            continue
        display_title = _metric_display_name(metric)
        slide_num = start_index + i

        b64 = cohort_monitoring_chart(
            df=df,
            metric=metric,
            risk_bands=risk_bands,
            band_column="risk_band",
            legend_map=cfg.legend_map,
            max_month=cfg.max_month,
            brand_color=brand_color,
        )

        slide_id = f"cohort-{metric.replace('_', '-')[:40]}"
        html = image_slide(
            slide_id=slide_id,
            section_label="Cohort Monitoring",
            title=f"Cohort Monitoring · {display_title}",
            b64=b64,
            alt=display_title,
        )

        abbrev = metric.replace("_", "-")[:50]
        filename = f"{slide_num:02d}-cohort-{abbrev}.html"
        slides.append((filename, html))

    return slides

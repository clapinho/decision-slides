"""Cohort monitoring slides — one slide per metric."""

from __future__ import annotations

from ..config import CohortMonitoringConfig, COHORT_METRICS
from ..charts import cohort_monitoring_chart
from .base import image_slide, BRAND_PURPLE


def fetch_data(client, cfg: CohortMonitoringConfig):
    """Fetch cohort monitoring data from the configured table."""
    bands_str = ",".join(str(b) for b in cfg.aki_bands)
    sql = f"""
        SELECT aki_band, cohort, month, {', '.join(m for m, _ in COHORT_METRICS)}
        FROM {cfg.table}
        WHERE aki_band IN ({bands_str})
          AND month <= {cfg.max_month}
        ORDER BY aki_band, cohort, month
    """
    import pandas as pd
    rows = client.query(sql)
    return pd.DataFrame(rows)


def generate_all(
    df,
    cfg: CohortMonitoringConfig,
    brand_color: str = BRAND_PURPLE,
    start_index: int = 1,
) -> list[tuple[str, str]]:
    """
    Generate one slide per metric.
    Returns list of (filename, html) pairs.
    """
    metrics = cfg.metrics if cfg.metrics else [m for m, _ in COHORT_METRICS]
    metric_titles = dict(COHORT_METRICS)

    slides = []
    slide_num = start_index

    for metric in metrics:
        if metric not in metric_titles:
            continue
        title = metric_titles[metric]
        display_title = title.replace("_", " ").title() if metric not in metric_titles else title

        b64 = cohort_monitoring_chart(
            df=df,
            metric=metric,
            aki_bands=cfg.aki_bands,
            legend_map=cfg.legend_map,
            max_month=cfg.max_month,
            brand_color=brand_color,
        )

        slide_id = f"cohort-{metric.replace('_', '-')[:40]}"
        html = image_slide(
            slide_id=slide_id,
            section_label=f"Cohort Monitoring",
            title=f"Cohort Monitoring · {display_title}",
            b64=b64,
            alt=display_title,
        )

        # Filename: use slide number prefix + abbreviated metric name
        abbrev = metric.replace("_", "-")[:50]
        filename = f"{slide_num:02d}-cohort-{abbrev}.html"
        slides.append((filename, html))
        slide_num += 1

    return slides

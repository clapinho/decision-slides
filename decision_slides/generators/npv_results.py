"""NPV results slide generator — queries 4 tables and plots a line/bar chart."""

from __future__ import annotations

from typing import Optional

from ..config import NpvTablesConfig
from ..charts import npv_line_chart, npv_bar_chart
from .base import image_slide, BRAND_PURPLE


def fetch_data(client, cfg: NpvTablesConfig) -> dict[str, dict[int, float]]:
    """Query all four NPV tables and return {type_label: {band: npv}}."""
    parts = []
    if cfg.current:
        parts.append(
            f"SELECT aki_band, CAST({cfg.npv_column_current} AS DOUBLE) AS npv, 'current' AS type "
            f"FROM {cfg.current} WHERE scenario_name = '{cfg.scenario_filter}' AND aki_band >= 21"
        )
    for table, label, col in [
        (cfg.pclip,   "pclip",   cfg.npv_column_others),
        (cfg.actuals, "actuals", cfg.npv_column_others),
        (cfg.sec,     "sec",     cfg.npv_column_others),
    ]:
        if table:
            parts.append(
                f"SELECT aki_band, CAST({col} AS DOUBLE) AS npv, '{label}' AS type "
                f"FROM {table} WHERE scenario_name = '{cfg.scenario_filter}' AND aki_band >= 21"
            )

    sql = " UNION ALL ".join(parts) + " ORDER BY aki_band, type"
    rows = client.query(sql)

    result: dict[str, dict[int, float]] = {}
    for row in rows:
        label = row["type"]
        band  = int(row["aki_band"])
        npv   = float(row["npv"]) if row["npv"] is not None else 0.0
        if label not in result:
            result[label] = {}
        if band in cfg.aki_bands:
            result[label][band] = npv
    return result


def generate(
    data: dict[str, dict[int, float]],
    chart_type: str = "line",
    title: str = "NPV by Aki Band · Risk Worsening Scenario",
    brand_color: str = BRAND_PURPLE,
) -> str:
    if chart_type == "bar":
        b64 = npv_bar_chart(data, title=title, brand_color=brand_color)
    else:
        b64 = npv_line_chart(data, title=title, brand_color=brand_color)

    return image_slide(
        slide_id="npv-results",
        section_label="NPV Results",
        title=title,
        b64=b64,
        alt="NPV Results",
        notes="NPV with management fee by aki band. Highlight tier boundary.",
    )

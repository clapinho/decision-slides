"""NPV results slide generator — queries multiple tables and plots a line/bar chart."""

from __future__ import annotations

from ..config import NpvTablesConfig
from ..charts import npv_line_chart, npv_bar_chart
from .base import image_slide, BRAND_PURPLE


def fetch_data(client, cfg: NpvTablesConfig) -> dict[str, dict[int, float]]:
    """
    Query each configured table and return {series_label: {band_value: npv}}.
    Series without a table name are skipped.
    """
    # Build (table, label) pairs from config
    series = [
        (cfg.current,  cfg.label_current),
        (cfg.series_2, cfg.label_series_2),
        (cfg.series_3, cfg.label_series_3),
        (cfg.series_4, cfg.label_series_4),
    ]

    parts = []
    for table, label in series:
        if not table:
            continue
        where_clauses = []
        if cfg.scenario_filter and cfg.scenario_column:
            where_clauses.append(
                f"{cfg.scenario_column} = '{cfg.scenario_filter}'"
            )
        where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        parts.append(
            f"SELECT {cfg.band_column} AS band, "
            f"CAST({cfg.npv_column} AS DOUBLE) AS npv, "
            f"'{label}' AS series "
            f"FROM {table} {where}"
        )

    if not parts:
        return {}

    sql = " UNION ALL ".join(parts) + f" ORDER BY band, series"
    rows = client.query(sql)

    result: dict[str, dict[int, float]] = {}
    for row in rows:
        label = row["series"]
        band = int(row["band"])
        npv = float(row["npv"]) if row["npv"] is not None else 0.0
        if cfg.risk_bands and band not in cfg.risk_bands:
            continue
        result.setdefault(label, {})[band] = npv
    return result


def generate(
    data: dict[str, dict[int, float]],
    chart_type: str = "line",
    title: str = "NPV by Risk Band",
    y_label: str = "NPV",
    band_label: str = "Band",
    brand_color: str = BRAND_PURPLE,
) -> str:
    if chart_type == "bar":
        b64 = npv_bar_chart(data, title=title, y_label=y_label,
                            band_label=band_label, brand_color=brand_color)
    else:
        b64 = npv_line_chart(data, title=title, y_label=y_label,
                             band_label=band_label, brand_color=brand_color)

    return image_slide(
        slide_id="npv-results",
        section_label="NPV Results",
        title=title,
        b64=b64,
        alt="NPV Results",
    )

"""Configuration dataclasses for a decision-slides build run."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class DatabricksConfig:
    workspace_url: str = ""
    token: str = ""
    warehouse_id: str = ""

    def is_set(self) -> bool:
        return bool(self.workspace_url and self.token and self.warehouse_id)


@dataclass
class NpvTablesConfig:
    """SQL table names for each model type used in NPV results."""
    # One entry per model type you want to compare; leave blank to skip that series.
    current: str = ""
    series_2: str = ""   # e.g. a challenger or alternative model
    series_3: str = ""
    series_4: str = ""
    # Series labels shown in the chart legend
    label_current: str = "current"
    label_series_2: str = "series 2"
    label_series_3: str = "series 3"
    label_series_4: str = "series 4"
    # SQL column that holds the NPV value (same name expected in every table)
    npv_column: str = "npv"
    # SQL column that holds the risk band identifier
    band_column: str = "risk_band"
    # Optional WHERE clause value for filtering by scenario; leave blank to skip
    scenario_column: str = "scenario_name"
    scenario_filter: str = ""
    # Risk band values to include (empty = include all returned by the query)
    risk_bands: list[int] = field(default_factory=list)
    chart_type: str = "line"  # "line" or "bar"


@dataclass
class CohortMonitoringConfig:
    table: str = ""
    # Risk band values to chart (empty = all bands returned by the query)
    risk_bands: list[int] = field(default_factory=list)
    # SQL column that holds the risk band identifier
    band_column: str = "risk_band"
    # Rename cohort labels in the legend: {original_column_value: display_name}
    # e.g. {"baseline": "Actuals", "challenger": "New Model"}
    legend_map: dict[str, str] = field(default_factory=dict)
    # Metric columns to chart; empty = chart all numeric columns found in the table
    metrics: list[str] = field(default_factory=list)
    max_month: int = 18


@dataclass
class NotebookRef:
    """Reference to a specific command inside a Databricks notebook."""
    notebook_url: str = ""
    command_number: int = 1  # 1-indexed, as shown in the Databricks UI

    def notebook_id(self) -> Optional[str]:
        """Extract numeric notebook ID from a Databricks URL."""
        import re
        m = re.search(r"/notebooks/(\d+)", self.notebook_url)
        return m.group(1) if m else None


@dataclass
class GoogleSlidesRef:
    presentation_url: str = ""

    def presentation_id(self) -> Optional[str]:
        import re
        m = re.search(r"/d/([a-zA-Z0-9_-]+)", self.presentation_url)
        return m.group(1) if m else None


@dataclass
class AppendixSource:
    source_type: str = "none"  # "google_slides" | "images" | "none"
    google_slides: Optional[GoogleSlidesRef] = None
    image_paths: list[str] = field(default_factory=list)


@dataclass
class PresentationConfig:
    name: str = ""
    title: str = ""
    squad: str = ""
    date: str = ""
    brand_color: str = "#7c3aed"
    output_dir: str = ""

    databricks: DatabricksConfig = field(default_factory=DatabricksConfig)

    # Per-slide references
    cover_image: str = ""
    executive_summary_text: dict = field(default_factory=dict)
    decision_overview: NotebookRef = field(default_factory=NotebookRef)
    tier_ii: NotebookRef = field(default_factory=NotebookRef)
    risks_text: dict = field(default_factory=dict)
    npv_results: NpvTablesConfig = field(default_factory=NpvTablesConfig)
    npv_levers: NotebookRef = field(default_factory=NotebookRef)
    iram: NotebookRef = field(default_factory=NotebookRef)
    roa: NotebookRef = field(default_factory=NotebookRef)
    curves_overview_type: str = "notebook"  # "notebook" | "google_slides"
    curves_overview_notebook: NotebookRef = field(default_factory=NotebookRef)
    curves_overview_slides: GoogleSlidesRef = field(default_factory=GoogleSlidesRef)
    cohort_monitoring: CohortMonitoringConfig = field(default_factory=CohortMonitoringConfig)
    appendix: AppendixSource = field(default_factory=AppendixSource)

    deploy: bool = False
    app_name: str = ""

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> "PresentationConfig":
        data = json.loads(path.read_text())
        cfg = cls()
        cfg.databricks = DatabricksConfig(**data.get("databricks", {}))
        cfg.npv_results = NpvTablesConfig(**data.get("npv_results", {}))
        cfg.cohort_monitoring = CohortMonitoringConfig(**data.get("cohort_monitoring", {}))
        for k, v in data.items():
            if hasattr(cfg, k) and not isinstance(v, dict):
                setattr(cfg, k, v)
        return cfg

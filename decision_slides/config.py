"""Configuration dataclasses for a decision-slides build run."""

from __future__ import annotations

import json
import os
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
    current: str = ""
    pclip: str = ""
    actuals: str = ""
    sec: str = ""
    npv_column_current: str = "npv_with_mgm"
    npv_column_others: str = "npv"
    scenario_filter: str = "risk-worsening"
    aki_bands: list[int] = field(default_factory=lambda: list(range(21, 31)))
    chart_type: str = "line"  # "line" or "bar"


@dataclass
class CohortMonitoringConfig:
    table: str = ""
    aki_bands: list[int] = field(default_factory=lambda: [21, 25, 26, 27, 28])
    # legend label renames: original key → display label
    legend_map: dict[str, str] = field(default_factory=lambda: {"static": "actuals", "running": "pClip"})
    # empty list = include all 23 metrics
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
    source_type: str = "google_slides"  # "google_slides" | "images" | "none"
    google_slides: Optional[GoogleSlidesRef] = None
    image_paths: list[str] = field(default_factory=list)


@dataclass
class PresentationConfig:
    name: str = ""
    title: str = ""
    squad: str = ""
    date: str = ""
    brand_color: str = "#820AD1"
    output_dir: str = ""

    databricks: DatabricksConfig = field(default_factory=DatabricksConfig)

    # Per-slide references
    cover_image: str = ""                          # local image path or Google Slides URL
    executive_summary_text: dict = field(default_factory=dict)  # {overview, results, to_discuss}
    decision_overview: NotebookRef = field(default_factory=NotebookRef)
    tier_ii: NotebookRef = field(default_factory=NotebookRef)
    tier_ii_aki_bands: list[int] = field(default_factory=lambda: list(range(21, 31)))
    risks_text: dict = field(default_factory=dict)  # {risks, opportunities}
    npv_results: NpvTablesConfig = field(default_factory=NpvTablesConfig)
    npv_levers: NotebookRef = field(default_factory=NotebookRef)
    npv_levers_commands: list[int] = field(default_factory=list)
    iram: NotebookRef = field(default_factory=NotebookRef)
    roa: NotebookRef = field(default_factory=NotebookRef)
    curves_overview_type: str = "google_slides"    # "notebook" | "google_slides"
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
        # Copy remaining scalar fields
        for k, v in data.items():
            if hasattr(cfg, k) and not isinstance(v, dict):
                setattr(cfg, k, v)
        return cfg


# ── Known metrics for cohort monitoring (in display order) ──────────────────
COHORT_METRICS: list[tuple[str, str]] = [
    ("risk_adjusted_margin_perfect_provisions_100_ftp",               "Risk Adjusted Margin (Perfect Provisions)"),
    ("cumulative_risk_adjusted_margin_perfect_provisions_100_ftp",    "Cumulative RAM (Perfect Provisions)"),
    ("cumulative_risk_adjusted_margin_perfect_provisions_100_ftp_per_total_revenue",
                                                                       "Cumulative RAM / Total Revenue"),
    ("rolled_risk_adjusted_margin_60_180",                            "Rolled RAM (60–180)"),
    ("cumulative_rolled_risk_adjusted_margin_60_180",                 "Cumulative Rolled RAM (60–180)"),
    ("credit_losses_released",                                        "Credit Losses Released"),
    ("cumulative_credit_losses_released",                             "Cumulative Credit Losses Released"),
    ("net_revenues_100_ftp",                                          "Net Revenues (100% FTP)"),
    ("gross_interest_revenue_released",                               "Gross Interest Revenue Released"),
    ("gross_non_interest_revenue_released",                           "Gross Non-Interest Revenue Released"),
    ("gross_revenue_released",                                        "Gross Revenue Released"),
    ("gross_interchange_revenue_released",                            "Gross Interchange Revenue Released"),
    ("cumulative_net_revenues_100_ftp",                               "Cumulative Net Revenues (100% FTP)"),
    ("rolled_losses_60_180",                                          "Rolled Losses (60–180)"),
    ("cumulative_rolled_losses_60_180",                               "Cumulative Rolled Losses (60–180)"),
    ("internal_delinquency_rate",                                     "Internal Delinquency Rate"),
    ("cumulative_internal_delinquency_rate",                          "Cumulative Internal Delinquency Rate"),
    ("lgd_ratio",                                                     "LGD Ratio"),
    ("ead_ratio",                                                      "EAD Ratio"),
    ("charge_off_balance",                                            "Charge-Off Balance"),
    ("credit_limit_per_open",                                         "Credit Limit per Open"),
    ("spend_utilization",                                             "Spend Utilization"),
    ("charged_late_fee",                                              "Charged Late Fee"),
]

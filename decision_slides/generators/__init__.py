"""Slide HTML generators — one module per slide type."""

from . import (
    base,
    cover,
    executive_summary,
    decision_overview,
    tier_ii,
    risks,
    npv_results,
    npv_levers,
    iram,
    roa,
    curves_overview,
    cohort_monitoring,
    appendix,
)

__all__ = [
    "base",
    "cover",
    "executive_summary",
    "decision_overview",
    "tier_ii",
    "risks",
    "npv_results",
    "npv_levers",
    "iram",
    "roa",
    "curves_overview",
    "cohort_monitoring",
    "appendix",
]

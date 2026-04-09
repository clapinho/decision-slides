# decision-slides

Interactive CLI wizard that builds and deploys credit decision presentations using the [slips](https://github.com/nicktindall/slipshow) framework and Databricks.

## Installation

```bash
pip install -e ".[google]"   # include Google Slides support
# or
pip install -e .
```

Requires Node.js and a slips repo at `~/slips` (override with `--slips-root`).

## Quick start

```bash
decision-slides new
```

The wizard prompts for every slide in the standard order:

| # | Slide | Input |
|---|-------|-------|
| 1 | Cover | Optional background image |
| 2 | Executive Summary | Free text — overview, findings, discussion items |
| 3 | Decision Overview | Databricks notebook URL + cell number |
| 4 | Tier II | Databricks notebook URL + cell number |
| 5 | Risks, Limitations & Opportunities | Free text lists |
| 6 | NPV Results | Up to 4 table names, column names, optional scenario filter |
| 7 | NPV Levers | Databricks notebook URL + cell number |
| 8 | iRAM | Databricks notebook URL + cell number |
| 9 | ROA | Databricks notebook URL + cell number |
| 10 | Curves Overview | Notebook **or** Google Slides presentation URL |
| 11 | Cohort Monitoring | Unity Catalog table, band column, optional metric/legend config |
| 12 | Appendix | Google Slides, local images, or nothing |

At the end it builds the presentation and optionally deploys it as a Databricks App.

## Save and re-run

```bash
# Run wizard once, save config
decision-slides new --save-config my-deck.yaml

# Rebuild without re-running the wizard
decision-slides build my-deck.yaml

# Deploy a previously built presentation
decision-slides deploy my-deck.yaml
```

## Notebook references

Paste the full Databricks URL when asked, e.g.:

```
https://<workspace>.cloud.databricks.com/browse/notebooks/123456789
```

The tool extracts the numeric notebook ID, exports it as Jupyter, and reads the PNG output of the specified cell (1-based index).

## NPV Results

Supports up to 4 model-type series. Each series maps to one SQL table:

| Config field | What it controls |
|---|---|
| `npv_column` | NPV value column (same name expected in every table) |
| `band_column` | Risk band column (e.g. `risk_band`, `score_band`, `tier`) |
| `scenario_column` / `scenario_filter` | Optional WHERE clause filter |
| `risk_bands` | Bands to include (empty = all) |
| `chart_type` | `line` or `bar` |

Series labels (shown in the legend) are fully configurable.

## Cohort Monitoring

One slide per metric column. All parameters are generic:

| Config field | Default | Notes |
|---|---|---|
| `band_column` | `risk_band` | Any column that identifies risk segments |
| `risk_bands` | all | Filter to specific band values |
| `legend_map` | `{}` | Rename overlay cohort labels for the chart legend |
| `metrics` | all numeric | Limit to specific columns |
| `max_month` | `18` | X-axis upper bound |

## Databricks App deployment

The built HTML is split into ≤4 MB chunks and uploaded as workspace `FILE` objects. The app serves them via Python's stdlib `http.server` — no extra dependencies needed.

## Environment variables

| Variable | Description |
|---|---|
| `DATABRICKS_HOST` | Workspace URL |
| `DATABRICKS_TOKEN` | Personal access token |
| `DATABRICKS_WAREHOUSE_ID` | SQL warehouse ID |

## Requirements

- Python ≥ 3.10
- Node.js (for slips build step)
- A slips presentation repo at `~/slips`

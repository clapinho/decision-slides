# decision-slides

Interactive CLI wizard that builds and deploys credit decision presentations using the [slips](https://github.com/nicktindall/slipshow) framework and Databricks.

## Installation

```bash
pip install -e ".[google]"   # include Google Slides support
# or
pip install -e .             # without Google Slides
```

Requires Node.js and the slips repo at `~/slips` (or pass `--slips-root`).

## Quick start

```bash
decision-slides new
```

The wizard walks you through every slide in the standard order:

| # | Slide | Input |
|---|-------|-------|
| 1 | Cover | Local image (optional) |
| 2 | Executive Summary | Free text |
| 3 | Decision Overview | Databricks notebook URL + cell number |
| 4 | Tier II | Databricks notebook URL + cell number |
| 5 | Risks, Limitations & Opportunities | Free text lists |
| 6 | NPV Results | Four table names + scenario filter |
| 7 | NPV Levers | Databricks notebook URL + cell number |
| 8 | iRAM | Databricks notebook URL + cell number |
| 9 | ROA | Databricks notebook URL + cell number |
| 10 | Curves Overview | Notebook or Google Slides URL |
| 11 | Cohort Monitoring | Unity Catalog table + band/metric filters |
| 12 | Appendix | Google Slides, local images, or nothing |

At the end, it builds the presentation with the slips CLI and optionally deploys it as a Databricks App.

## Saving and re-running

```bash
decision-slides new --save-config my-presentation.yaml
decision-slides build my-presentation.yaml
decision-slides deploy my-presentation.yaml
```

## Notebook references

When asked for a "notebook URL", paste the full Databricks URL, e.g.:

```
https://nubank-e2-credit-strategy.cloud.databricks.com/browse/notebooks/474934422131980
```

The wizard extracts the numeric notebook ID and exports it as a Jupyter notebook to read the cell output image (PNG) at the given command/cell number (1-based).

## NPV Results

The NPV Results slide queries up to four tables:

| Table | Column |
|-------|--------|
| Current model | `npv_with_mgm` (configurable) |
| pClip | `npv` (configurable) |
| Actuals | `npv` |
| SEC | `npv` |

All tables are filtered by `scenario_name = '<filter>'` and `aki_band >= 21`.

## Cohort Monitoring

One slide is generated per metric. Defaults:
- Bands: 21–30
- Legend: `static → actuals`, `running → pClip`
- Metrics: all 23 cohort metrics (or a custom subset)

## Databricks App deployment

The built HTML is split into ≤4 MB chunks and uploaded as workspace `FILE` objects. The app serves them via Python's stdlib `http.server` — no external dependencies required.

## Environment variables

| Variable | Description |
|----------|-------------|
| `DATABRICKS_HOST` | Workspace URL |
| `DATABRICKS_TOKEN` | Personal access token |
| `DATABRICKS_WAREHOUSE_ID` | SQL warehouse ID |

## Requirements

- Python ≥ 3.10
- Node.js (for slips build step)
- `~/slips` — the slips presentation repo

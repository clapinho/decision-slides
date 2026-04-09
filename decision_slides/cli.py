"""
decision-slides CLI

Interactive wizard to build and deploy credit decision presentations.
"""

from __future__ import annotations

import os
import sys
import base64
import datetime
from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.prompt import Prompt, Confirm, IntPrompt

from .config import (
    DatabricksConfig,
    NpvTablesConfig,
    CohortMonitoringConfig,
    NotebookRef,
    GoogleSlidesRef,
)
from .databricks_client import DatabricksClient
from .generators import (
    cover as gen_cover,
    executive_summary as gen_exec,
    decision_overview as gen_decision,
    tier_ii as gen_tier,
    risks as gen_risks,
    npv_results as gen_npv,
    npv_levers as gen_levers,
    iram as gen_iram,
    roa as gen_roa,
    curves_overview as gen_curves,
    cohort_monitoring as gen_cohort,
    appendix as gen_appendix,
)
from .assembler import assemble
from .deployer import build_presentation, deploy

console = Console()
BRAND_PURPLE = "#7c3aed"


# ──────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────

def _header(title: str) -> None:
    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="dim"))


def _ok(text: str) -> None:
    console.print(f"  [green]✓[/green] {text}")


def _warn(text: str) -> None:
    console.print(f"  [yellow]![/yellow] {text}")


def _err(text: str) -> None:
    console.print(f"  [red]✗[/red] {text}")


def _ask(question: str, default: str = "", password: bool = False) -> str:
    return Prompt.ask(f"  {question}", default=default, password=password)


def _ask_int(question: str, default: int = 1) -> int:
    return IntPrompt.ask(f"  {question}", default=default)


def _ask_yn(question: str, default: bool = False) -> bool:
    return Confirm.ask(f"  {question}", default=default)


def _ask_list(question: str, hint: str = "one item per line, blank line to finish") -> list[str]:
    console.print(f"  {question} [dim]({hint})[/dim]")
    items = []
    while True:
        val = input("    > ").strip()
        if not val:
            break
        items.append(val)
    return items


def _ask_notebook(label: str) -> NotebookRef:
    url = _ask(f"{label} notebook URL")
    cmd = _ask_int(f"{label} command/cell number (1-based)", default=1)
    return NotebookRef(notebook_url=url, command_number=cmd)


def _ask_google_slides() -> tuple[GoogleSlidesRef, str]:
    url = _ask("Google Slides presentation URL")
    token = _ask("Google OAuth access token (drive.readonly scope)", password=True)
    return GoogleSlidesRef(presentation_url=url), token


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

@click.group()
@click.version_option("0.1.0", prog_name="decision-slides")
def main():
    """Build and deploy credit decision presentations."""


@main.command()
@click.option("--slips-root", type=click.Path(), default=None,
              help="Path to your slips repo (default: ~/slips)")
@click.option("--save-config", "config_out", type=click.Path(), default=None,
              help="Save config to this YAML file so you can rebuild without re-running the wizard")
def new(slips_root, config_out):
    """Interactive wizard — build a new decision presentation."""

    console.print(Panel.fit(
        "[bold]decision-slides[/bold] · Credit Decision Wizard",
        border_style="dim",
    ))

    slips_path = Path(slips_root) if slips_root else Path.home() / "slips"

    # ── Databricks ────────────────────────────
    _header("Databricks")
    workspace_url = _ask("Workspace URL", default=os.environ.get("DATABRICKS_HOST", ""))
    token = _ask("Personal access token", default=os.environ.get("DATABRICKS_TOKEN", ""), password=True)
    warehouse_id = _ask("SQL warehouse ID", default=os.environ.get("DATABRICKS_WAREHOUSE_ID", ""))

    db_cfg = DatabricksConfig(workspace_url=workspace_url.rstrip("/"), token=token, warehouse_id=warehouse_id)
    client = DatabricksClient(db_cfg)

    # ── Presentation metadata ─────────────────
    _header("Presentation")
    pres_name = _ask("Folder name (no spaces)", default="decision-slides")
    pres_title = _ask("Presentation title", default=pres_name.replace("-", " ").title())
    squad = _ask("Squad / team name", default="")
    date = _ask("Date", default=datetime.date.today().isoformat())
    exec_tag = _ask("Executive summary section tag (leave blank to hide)", default="")

    # ── Cover ─────────────────────────────────
    _header("Cover")
    cover_image_path = _ask("Cover background image path (leave blank to skip)", default="")
    cover_image_b64: Optional[str] = None
    if cover_image_path and Path(cover_image_path).exists():
        cover_image_b64 = base64.b64encode(Path(cover_image_path).read_bytes()).decode()
        _ok(f"Loaded cover image")
    elif cover_image_path:
        _warn("File not found — cover will use a gradient background")

    # ── Executive Summary ─────────────────────
    _header("Executive Summary")
    overview = _ask("Overview paragraph")
    results = _ask_list("Results / findings (bullet points)")
    to_discuss = _ask_list("Items to discuss")

    # ── Decision Overview ─────────────────────
    _header("Decision Overview")
    decision_notebook = _ask_notebook("Decision Overview")
    decision_title = _ask("Slide title", default="Decision Overview")

    # ── Tier II ───────────────────────────────
    _header("Tier II")
    tier_notebook = _ask_notebook("Tier II")
    tier_title = _ask("Slide title", default="Tier II Analysis")

    # ── Risks / Limitations / Opportunities ───
    _header("Risks, Limitations & Opportunities")
    risks_list = _ask_list("Risks")
    lim_list = _ask_list("Limitations")
    opp_list = _ask_list("Opportunities")

    # ── NPV Results ───────────────────────────
    _header("NPV Results")
    console.print("  [dim]Provide up to 4 model-type tables to compare. Leave table blank to skip a series.[/dim]")
    npv_col = _ask("NPV column name (same in every table)", default="npv")
    npv_band_col = _ask("Risk band column name", default="risk_band")
    npv_scenario_col = _ask("Scenario column name (blank to skip filter)", default="scenario_name")
    npv_scenario = _ask("Scenario filter value (blank = no filter)", default="")
    npv_current = _ask("Series 1 — table name", default="")
    npv_label_1 = _ask("Series 1 — legend label", default="current") if npv_current else ""
    npv_s2 = _ask("Series 2 — table name (blank to skip)", default="")
    npv_label_2 = _ask("Series 2 — legend label", default="series 2") if npv_s2 else ""
    npv_s3 = _ask("Series 3 — table name (blank to skip)", default="")
    npv_label_3 = _ask("Series 3 — legend label", default="series 3") if npv_s3 else ""
    npv_s4 = _ask("Series 4 — table name (blank to skip)", default="")
    npv_label_4 = _ask("Series 4 — legend label", default="series 4") if npv_s4 else ""
    npv_bands_raw = _ask("Risk bands to include (comma-separated, blank = all)", default="")
    npv_bands = [int(b.strip()) for b in npv_bands_raw.split(",") if b.strip().isdigit()]
    npv_chart = _ask("Chart type (line / bar)", default="line")
    npv_y_label = _ask("Y-axis label", default="NPV")
    npv_band_label = _ask("Band label on x-axis", default="Band")
    npv_slide_title = _ask("Slide title", default="NPV by Risk Band")

    npv_cfg = NpvTablesConfig(
        current=npv_current, series_2=npv_s2, series_3=npv_s3, series_4=npv_s4,
        label_current=npv_label_1 or "current",
        label_series_2=npv_label_2 or "series 2",
        label_series_3=npv_label_3 or "series 3",
        label_series_4=npv_label_4 or "series 4",
        npv_column=npv_col, band_column=npv_band_col,
        scenario_column=npv_scenario_col, scenario_filter=npv_scenario,
        risk_bands=npv_bands, chart_type=npv_chart,
    )

    # ── NPV Levers ────────────────────────────
    _header("NPV Levers")
    levers_notebook = _ask_notebook("NPV Levers")
    levers_title = _ask("Slide title", default="NPV Levers")

    # ── iRAM ──────────────────────────────────
    _header("iRAM")
    iram_notebook = _ask_notebook("iRAM")
    iram_title = _ask("Slide title", default="iRAM Analysis")

    # ── ROA ───────────────────────────────────
    _header("ROA")
    roa_notebook = _ask_notebook("ROA")
    roa_title = _ask("Slide title", default="ROA Analysis")

    # ── Curves Overview ───────────────────────
    _header("Curves Overview")
    curves_source = _ask("Source (notebook / google-slides)", default="notebook").strip().lower()
    curves_notebook: Optional[NotebookRef] = None
    curves_google: Optional[GoogleSlidesRef] = None
    curves_google_token: str = ""
    curves_title = "Curves Overview"
    if curves_source.startswith("g"):
        curves_google, curves_google_token = _ask_google_slides()
    else:
        curves_notebook = _ask_notebook("Curves Overview")
        curves_title = _ask("Slide title", default="Curves Overview")

    # ── Cohort Monitoring ─────────────────────
    _header("Cohort Monitoring")
    cohort_table = _ask("Table name (catalog.schema.table)")
    cohort_band_col = _ask("Risk band column name", default="risk_band")
    cohort_bands_raw = _ask("Risk bands to include (comma-separated, blank = all)", default="")
    cohort_bands = [int(b.strip()) for b in cohort_bands_raw.split(",") if b.strip().isdigit()]
    cohort_max_month = _ask_int("Max month", default=18)

    console.print("  [dim]Overlay rows are non-cohort rows (e.g. a static baseline or running challenger).[/dim]")
    has_overlays = _ask_yn("Does your data have overlay / baseline rows?", default=False)
    legend_map: dict[str, str] = {}
    if has_overlays:
        console.print("  [dim]Enter original cohort value → display label (blank to finish)[/dim]")
        while True:
            orig = _ask("  Original value (blank to finish)", default="")
            if not orig:
                break
            display = _ask(f"  Display label for '{orig}'", default=orig)
            legend_map[orig] = display

    cohort_metrics_raw = _ask("Metric columns to chart (comma-separated, blank = all numeric columns)", default="")
    cohort_metrics = [m.strip() for m in cohort_metrics_raw.split(",") if m.strip()]

    cohort_cfg = CohortMonitoringConfig(
        table=cohort_table,
        risk_bands=cohort_bands,
        band_column=cohort_band_col,
        legend_map=legend_map,
        metrics=cohort_metrics,
        max_month=cohort_max_month,
    )

    # ── Appendix ──────────────────────────────
    _header("Appendix")
    appendix_choice = _ask("What to include? (google-slides / images / none)", default="none").strip().lower()
    appendix_google: Optional[GoogleSlidesRef] = None
    appendix_google_token: str = ""
    appendix_image_paths: list[str] = []
    if appendix_choice.startswith("g"):
        appendix_google, appendix_google_token = _ask_google_slides()
    elif appendix_choice.startswith("i"):
        img_dir = _ask("Directory or comma-separated file paths")
        if "," in img_dir:
            appendix_image_paths = [p.strip() for p in img_dir.split(",")]
        else:
            d = Path(img_dir)
            if d.is_dir():
                appendix_image_paths = [
                    str(p) for p in sorted(d.iterdir())
                    if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}
                ]
            else:
                _warn(f"Directory not found: {img_dir}")

    # ── Build & deploy ────────────────────────
    _header("Build & Deploy")
    do_deploy = _ask_yn("Deploy to Databricks App after building?", default=False)
    app_name = _ask("App name", default=f"{pres_name}-slides") if do_deploy else ""

    # ── Save config ───────────────────────────
    cfg_dict = _collect_config(locals())
    if config_out:
        Path(config_out).write_text(
            yaml.dump(cfg_dict, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        _ok(f"Config saved → {config_out}")

    # ── Generate slides ───────────────────────
    _header("Generating slides")
    slides = _generate_slides(
        client=client,
        pres_title=pres_title, squad=squad, date=date,
        cover_image_b64=cover_image_b64,
        overview=overview, results=results, to_discuss=to_discuss, exec_tag=exec_tag,
        decision_notebook=decision_notebook, decision_title=decision_title,
        tier_notebook=tier_notebook, tier_title=tier_title,
        risks_list=risks_list, lim_list=lim_list, opp_list=opp_list,
        npv_cfg=npv_cfg, npv_slide_title=npv_slide_title,
        npv_y_label=npv_y_label, npv_band_label=npv_band_label, npv_chart=npv_chart,
        levers_notebook=levers_notebook, levers_title=levers_title,
        iram_notebook=iram_notebook, iram_title=iram_title,
        roa_notebook=roa_notebook, roa_title=roa_title,
        curves_notebook=curves_notebook, curves_google=curves_google,
        curves_google_token=curves_google_token, curves_title=curves_title,
        cohort_cfg=cohort_cfg,
        appendix_google=appendix_google, appendix_google_token=appendix_google_token,
        appendix_image_paths=appendix_image_paths, appendix_choice=appendix_choice,
    )

    pres_dir = assemble(pres_name, slides, pres_title, slips_path / "presentations")
    _ok(f"Assembled {len(slides)} slides → {pres_dir}")

    # ── Build ─────────────────────────────────
    _header("Building")
    try:
        built_html = build_presentation(pres_name, slips_path)
        _ok(f"Built: {built_html} ({built_html.stat().st_size / 1e6:.1f} MB)")
    except Exception as exc:
        _err(f"Build failed: {exc}")
        _warn("Make sure Node.js and the slips CLI are installed.")
        sys.exit(1)

    # ── Deploy ────────────────────────────────
    if do_deploy:
        _header("Deploying")
        try:
            url = deploy(
                client=client, app_name=app_name, built_html=built_html,
                description=f"{pres_title} — decision slides", progress_callback=_ok,
            )
            console.print()
            console.print(Panel(f"[bold green]Live at:[/bold green] {url}", border_style="green"))
        except Exception as exc:
            _err(f"Deploy failed: {exc}")
            sys.exit(1)
    else:
        console.print()
        _ok(f"Presentation ready at: {pres_dir}")


# ──────────────────────────────────────────────

@main.command("build")
@click.argument("config_file", type=click.Path(exists=True))
@click.option("--slips-root", type=click.Path(), default=None)
def build_cmd(config_file, slips_root):
    """Build presentation from a saved config YAML file."""
    slips_path = Path(slips_root) if slips_root else Path.home() / "slips"
    cfg = yaml.safe_load(Path(config_file).read_text(encoding="utf-8"))
    db = cfg["databricks"]
    client = DatabricksClient(DatabricksConfig(**db))

    _header("Building from config")
    slides = _generate_slides_from_dict(client, cfg)
    pres_dir = assemble(cfg["name"], slides, cfg["title"], slips_path / "presentations")
    _ok(f"Assembled {len(slides)} slides → {pres_dir}")
    built_html = build_presentation(cfg["name"], slips_path)
    _ok(f"Built: {built_html} ({built_html.stat().st_size / 1e6:.1f} MB)")


@main.command("deploy")
@click.argument("config_file", type=click.Path(exists=True))
@click.option("--slips-root", type=click.Path(), default=None)
def deploy_cmd(config_file, slips_root):
    """Deploy a previously built presentation to Databricks Apps."""
    slips_path = Path(slips_root) if slips_root else Path.home() / "slips"
    cfg = yaml.safe_load(Path(config_file).read_text(encoding="utf-8"))
    db = cfg["databricks"]
    client = DatabricksClient(DatabricksConfig(**db))
    name = cfg["name"]
    built_html = slips_path / "presentations" / f"{name}.built.html"
    if not built_html.exists():
        _err(f"Built file not found: {built_html}. Run `decision-slides build` first.")
        sys.exit(1)
    app_name = cfg.get("app_name", f"{name}-slides")
    _header("Deploying")
    url = deploy(
        client=client, app_name=app_name, built_html=built_html,
        description=f"{cfg.get('title', name)} — decision slides", progress_callback=_ok,
    )
    console.print()
    console.print(Panel(f"[bold green]Live at:[/bold green] {url}", border_style="green"))


# ──────────────────────────────────────────────
# slide generation
# ──────────────────────────────────────────────

def _generate_slides(
    client: DatabricksClient,
    pres_title: str,
    squad: str,
    date: str,
    cover_image_b64: Optional[str],
    overview: str,
    results: list[str],
    to_discuss: list[str],
    exec_tag: str,
    decision_notebook: NotebookRef,
    decision_title: str,
    tier_notebook: NotebookRef,
    tier_title: str,
    risks_list: list[str],
    lim_list: list[str],
    opp_list: list[str],
    npv_cfg: NpvTablesConfig,
    npv_slide_title: str,
    npv_y_label: str,
    npv_band_label: str,
    npv_chart: str,
    levers_notebook: NotebookRef,
    levers_title: str,
    iram_notebook: NotebookRef,
    iram_title: str,
    roa_notebook: NotebookRef,
    roa_title: str,
    curves_notebook: Optional[NotebookRef],
    curves_google: Optional[GoogleSlidesRef],
    curves_google_token: str,
    curves_title: str,
    cohort_cfg: CohortMonitoringConfig,
    appendix_google: Optional[GoogleSlidesRef],
    appendix_google_token: str,
    appendix_image_paths: list[str],
    appendix_choice: str,
) -> list[tuple[str, str]]:

    slides: list[tuple[str, str]] = []

    def _nb_slide(filename, gen_fn, notebook, title, slide_id, section):
        try:
            html = gen_fn(client, notebook, title=title)
            slides.append((filename, html))
            _ok(title)
        except Exception as e:
            _warn(f"{title} fetch failed ({e}) — placeholder inserted")
            slides.append((filename, _placeholder(slide_id, section, title)))

    # 1. Cover
    console.print("  [dim]→[/dim] Cover …")
    slides.append(("01-cover.html", gen_cover.generate(pres_title, squad, date, cover_image_b64)))

    # 2. Executive Summary
    console.print("  [dim]→[/dim] Executive Summary …")
    slides.append(("02-executive-summary.html",
        gen_exec.generate(overview, results, to_discuss, tag=exec_tag)))

    # 3–4. Notebook slides
    _nb_slide("03-decision-overview.html", gen_decision.generate_from_notebook,
              decision_notebook, decision_title, "decision-overview", "Decision Overview")
    _nb_slide("04-tier-ii.html", gen_tier.generate_from_notebook,
              tier_notebook, tier_title, "tier-ii", "Tier II")

    # 5. Risks
    console.print("  [dim]→[/dim] Risks …")
    slides.append(("05-risks-limitations-opportunities.html",
        gen_risks.generate(risks_list, lim_list, opp_list)))

    # 6. NPV Results
    console.print("  [dim]→[/dim] NPV Results …")
    try:
        npv_data = gen_npv.fetch_data(client, npv_cfg)
        slides.append(("06-npv-results.html",
            gen_npv.generate(npv_data, chart_type=npv_chart, title=npv_slide_title,
                             y_label=npv_y_label, band_label=npv_band_label)))
        _ok("NPV Results")
    except Exception as e:
        _warn(f"NPV Results failed ({e}) — placeholder")
        slides.append(("06-npv-results.html", _placeholder("npv-results", "NPV Results", npv_slide_title)))

    # 7–9. More notebook slides
    _nb_slide("07-npv-levers.html", gen_levers.generate_from_notebook,
              levers_notebook, levers_title, "npv-levers", "NPV Levers")
    _nb_slide("08-iram.html", gen_iram.generate_from_notebook,
              iram_notebook, iram_title, "iram", "iRAM")
    _nb_slide("09-roa.html", gen_roa.generate_from_notebook,
              roa_notebook, roa_title, "roa", "ROA")

    # 10. Curves Overview
    console.print("  [dim]→[/dim] Curves Overview …")
    try:
        if curves_google:
            for i, (_, html) in enumerate(
                gen_curves.generate_from_google_slides(curves_google, curves_google_token), 1
            ):
                slides.append((f"10-curves-{i:02d}.html", html))
        else:
            slides.append(("10-curves-overview.html",
                gen_curves.generate_from_notebook(client, curves_notebook, title=curves_title)))
        _ok("Curves Overview")
    except Exception as e:
        _warn(f"Curves Overview failed ({e}) — placeholder")
        slides.append(("10-curves-overview.html",
            _placeholder("curves-overview", "Curves Overview", curves_title)))

    # 11. Cohort Monitoring
    console.print("  [dim]→[/dim] Cohort Monitoring (fetching data) …")
    try:
        cohort_df = gen_cohort.fetch_data(client, cohort_cfg)
        cohort_slides = gen_cohort.generate_all(cohort_df, cohort_cfg)
        for i, (fn, html) in enumerate(cohort_slides):
            slides.append((f"11-{i + 1:02d}-{fn}", html))
        _ok(f"Cohort Monitoring ({len(cohort_slides)} metrics)")
    except Exception as e:
        _warn(f"Cohort Monitoring failed ({e}) — placeholder")
        slides.append(("11-cohort-monitoring.html",
            _placeholder("cohort-monitoring", "Cohort Monitoring", "Cohort Monitoring")))

    # 12. Appendix
    if not appendix_choice.startswith("n"):
        console.print("  [dim]→[/dim] Appendix …")
        slides.append(gen_appendix.section_header())
        try:
            if appendix_google:
                app_slides = gen_appendix.from_google_slides(
                    appendix_google.presentation_id(), appendix_google_token)
                slides.extend(app_slides)
                _ok(f"Appendix ({len(app_slides)} slides)")
            elif appendix_image_paths:
                app_slides = gen_appendix.from_image_paths(appendix_image_paths)
                slides.extend(app_slides)
                _ok(f"Appendix ({len(app_slides)} images)")
        except Exception as e:
            _warn(f"Appendix failed ({e})")

    return slides


def _generate_slides_from_dict(client: DatabricksClient, cfg: dict) -> list[tuple[str, str]]:
    def _nb(d):
        return NotebookRef(**d) if d else NotebookRef()

    def _gs(d):
        return GoogleSlidesRef(**d) if d else None

    npv = cfg.get("npv_results", {})
    npv_cfg = NpvTablesConfig(
        current=npv.get("current", ""),
        series_2=npv.get("series_2", ""),
        series_3=npv.get("series_3", ""),
        series_4=npv.get("series_4", ""),
        label_current=npv.get("label_current", "current"),
        label_series_2=npv.get("label_series_2", "series 2"),
        label_series_3=npv.get("label_series_3", "series 3"),
        label_series_4=npv.get("label_series_4", "series 4"),
        npv_column=npv.get("npv_column", "npv"),
        band_column=npv.get("band_column", "risk_band"),
        scenario_column=npv.get("scenario_column", "scenario_name"),
        scenario_filter=npv.get("scenario_filter", ""),
        risk_bands=npv.get("risk_bands", []),
        chart_type=npv.get("chart_type", "line"),
    )
    cm = cfg.get("cohort_monitoring", {})
    cohort_cfg = CohortMonitoringConfig(
        table=cm.get("table", ""),
        risk_bands=cm.get("risk_bands", []),
        band_column=cm.get("band_column", "risk_band"),
        legend_map=cm.get("legend_map", {}),
        metrics=cm.get("metrics", []),
        max_month=cm.get("max_month", 18),
    )
    co = cfg.get("curves_overview", {})
    curves_nb = _nb(co.get("notebook")) if co.get("notebook") else None
    curves_gs = _gs(co.get("google_slides"))
    ap = cfg.get("appendix", {})

    cover_image_b64 = None
    if cfg.get("cover_image_path"):
        p = Path(cfg["cover_image_path"])
        if p.exists():
            cover_image_b64 = base64.b64encode(p.read_bytes()).decode()

    es = cfg.get("executive_summary", {})
    return _generate_slides(
        client=client,
        pres_title=cfg["title"], squad=cfg.get("squad", ""), date=cfg.get("date", ""),
        cover_image_b64=cover_image_b64,
        overview=es.get("overview", ""), results=es.get("results", []),
        to_discuss=es.get("to_discuss", []), exec_tag=es.get("tag", ""),
        decision_notebook=_nb(cfg.get("decision_overview", {}).get("notebook")),
        decision_title=cfg.get("decision_overview", {}).get("title", "Decision Overview"),
        tier_notebook=_nb(cfg.get("tier_ii", {}).get("notebook")),
        tier_title=cfg.get("tier_ii", {}).get("title", "Tier II Analysis"),
        risks_list=cfg.get("risks_limitations_opportunities", {}).get("risks", []),
        lim_list=cfg.get("risks_limitations_opportunities", {}).get("limitations", []),
        opp_list=cfg.get("risks_limitations_opportunities", {}).get("opportunities", []),
        npv_cfg=npv_cfg,
        npv_slide_title=npv.get("title", "NPV by Risk Band"),
        npv_y_label=npv.get("y_label", "NPV"),
        npv_band_label=npv.get("band_label", "Band"),
        npv_chart=npv.get("chart_type", "line"),
        levers_notebook=_nb(cfg.get("npv_levers", {}).get("notebook")),
        levers_title=cfg.get("npv_levers", {}).get("title", "NPV Levers"),
        iram_notebook=_nb(cfg.get("iram", {}).get("notebook")),
        iram_title=cfg.get("iram", {}).get("title", "iRAM Analysis"),
        roa_notebook=_nb(cfg.get("roa", {}).get("notebook")),
        roa_title=cfg.get("roa", {}).get("title", "ROA Analysis"),
        curves_notebook=curves_nb,
        curves_google=curves_gs,
        curves_google_token=co.get("google_token", ""),
        curves_title=co.get("title", "Curves Overview"),
        cohort_cfg=cohort_cfg,
        appendix_google=_gs(ap.get("google_slides")),
        appendix_google_token=ap.get("google_token", ""),
        appendix_image_paths=ap.get("image_paths", []),
        appendix_choice=ap.get("type", "none"),
    )


def _collect_config(ctx: dict) -> dict:
    nb = ctx.get
    def _nb_dict(ref: Optional[NotebookRef]):
        return {"notebook_url": ref.notebook_url, "command_number": ref.command_number} if ref else None

    return {
        "name": ctx["pres_name"],
        "title": ctx["pres_title"],
        "squad": ctx["squad"],
        "date": ctx["date"],
        "cover_image_path": ctx["cover_image_path"],
        "databricks": {
            "workspace_url": ctx["workspace_url"],
            "token": ctx["token"],
            "warehouse_id": ctx["warehouse_id"],
        },
        "executive_summary": {
            "tag": ctx["exec_tag"],
            "overview": ctx["overview"],
            "results": ctx["results"],
            "to_discuss": ctx["to_discuss"],
        },
        "decision_overview": {
            "notebook": _nb_dict(ctx["decision_notebook"]),
            "title": ctx["decision_title"],
        },
        "tier_ii": {
            "notebook": _nb_dict(ctx["tier_notebook"]),
            "title": ctx["tier_title"],
        },
        "risks_limitations_opportunities": {
            "risks": ctx["risks_list"],
            "limitations": ctx["lim_list"],
            "opportunities": ctx["opp_list"],
        },
        "npv_results": {
            "title": ctx["npv_slide_title"],
            "y_label": ctx["npv_y_label"],
            "band_label": ctx["npv_band_label"],
            "chart_type": ctx["npv_chart"],
            "npv_column": ctx["npv_col"],
            "band_column": ctx["npv_band_col"],
            "scenario_column": ctx["npv_scenario_col"],
            "scenario_filter": ctx["npv_scenario"],
            "current": ctx["npv_current"],
            "label_current": ctx["npv_label_1"],
            "series_2": ctx["npv_s2"],
            "label_series_2": ctx["npv_label_2"],
            "series_3": ctx["npv_s3"],
            "label_series_3": ctx["npv_label_3"],
            "series_4": ctx["npv_s4"],
            "label_series_4": ctx["npv_label_4"],
            "risk_bands": ctx["npv_bands"],
        },
        "npv_levers": {
            "notebook": _nb_dict(ctx["levers_notebook"]),
            "title": ctx["levers_title"],
        },
        "iram": {
            "notebook": _nb_dict(ctx["iram_notebook"]),
            "title": ctx["iram_title"],
        },
        "roa": {
            "notebook": _nb_dict(ctx["roa_notebook"]),
            "title": ctx["roa_title"],
        },
        "curves_overview": {
            "notebook": _nb_dict(ctx["curves_notebook"]),
            "google_slides": (
                {"presentation_url": ctx["curves_google"].presentation_url}
                if ctx["curves_google"] else None
            ),
            "google_token": ctx["curves_google_token"],
            "title": ctx["curves_title"],
        },
        "cohort_monitoring": {
            "table": ctx["cohort_table"],
            "risk_bands": ctx["cohort_bands"],
            "band_column": ctx["cohort_band_col"],
            "max_month": ctx["cohort_max_month"],
            "legend_map": ctx["legend_map"],
            "metrics": ctx["cohort_metrics"],
        },
        "appendix": {
            "type": ctx["appendix_choice"],
            "google_slides": (
                {"presentation_url": ctx["appendix_google"].presentation_url}
                if ctx["appendix_google"] else None
            ),
            "google_token": ctx["appendix_google_token"],
            "image_paths": ctx["appendix_image_paths"],
        },
        "app_name": ctx["app_name"],
    }


def _placeholder(slide_id: str, section_label: str, title: str) -> str:
    return f"""<slip-slide id="{slide_id}" transition="fade">
  <style>
    .ph-root {{
      height: 100%; background: #f9fafb; display: flex; flex-direction: column;
      align-items: center; justify-content: center; gap: 1rem;
      font-family: var(--slip-font);
    }}
    .ph-label {{ font-size: 0.7rem; color: #9ca3af; letter-spacing: 0.08em; text-transform: uppercase; }}
    .ph-title {{ font-size: 1.6rem; font-weight: 700; color: {BRAND_PURPLE}; }}
    .ph-note {{ font-size: 0.8rem; color: #d1d5db; }}
  </style>
  <div class="ph-root">
    <div class="ph-label">{section_label}</div>
    <div class="ph-title">{title}</div>
    <div class="ph-note">[placeholder — data fetch failed]</div>
  </div>
</slip-slide>
"""

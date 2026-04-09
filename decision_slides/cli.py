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
from rich.text import Text
from rich.prompt import Prompt, Confirm, IntPrompt

from .config import (
    DatabricksConfig,
    NpvTablesConfig,
    CohortMonitoringConfig,
    NotebookRef,
    GoogleSlidesRef,
    COHORT_METRICS,
)
from .databricks_client import DatabricksClient
from . import generators
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


def _sub(text: str) -> None:
    console.print(f"  [dim]{text}[/dim]")


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


def _ask_list(question: str, hint: str = "one item per line, empty line to finish") -> list[str]:
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


def _ask_google_slides(label: str = "Google Slides") -> tuple[GoogleSlidesRef, str]:
    url = _ask(f"{label} presentation URL")
    token = _ask(f"Google OAuth access token (drive.readonly scope)", password=True)
    return GoogleSlidesRef(presentation_url=url), token


def _save_config(cfg: dict, path: Path) -> None:
    path.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


# ──────────────────────────────────────────────
# CLI entry-point
# ──────────────────────────────────────────────

@click.group()
@click.version_option("0.1.0", prog_name="decision-slides")
def main():
    """Build and deploy credit decision presentations."""


@main.command()
@click.option("--slips-root", type=click.Path(), default=None,
              help="Path to your slips repo (default: ~/slips)")
@click.option("--save-config", "config_out", type=click.Path(), default=None,
              help="Save collected config to this YAML file")
def new(slips_root, config_out):
    """Interactive wizard — build a new decision presentation."""

    console.print(Panel.fit(
        "[bold]decision-slides[/bold] · Credit Decision Wizard",
        border_style="dim",
    ))

    slips_path = Path(slips_root) if slips_root else Path.home() / "slips"

    # ── Databricks config ─────────────────────
    _header("Databricks")
    workspace_url = _ask(
        "Workspace URL",
        default=os.environ.get("DATABRICKS_HOST", ""),
    )
    token = _ask(
        "Personal access token",
        default=os.environ.get("DATABRICKS_TOKEN", ""),
        password=True,
    )
    warehouse_id = _ask(
        "SQL warehouse ID",
        default=os.environ.get("DATABRICKS_WAREHOUSE_ID", ""),
    )

    db_cfg = DatabricksConfig(
        workspace_url=workspace_url.rstrip("/"),
        token=token,
        warehouse_id=warehouse_id,
    )
    client = DatabricksClient(db_cfg)

    # ── Presentation metadata ─────────────────
    _header("Presentation")
    pres_name = _ask("Presentation name (used as folder name, no spaces)", default="decision-slides")
    pres_title = _ask("Presentation title", default=pres_name.replace("-", " ").title())
    squad = _ask("Squad / team name", default="Credit Strategy")
    date = _ask("Date", default=datetime.date.today().isoformat())

    # ── Cover ─────────────────────────────────
    _header("Cover slide")
    cover_image_path = _ask(
        "Cover image path (local PNG/JPEG, leave blank to skip)",
        default="",
    )
    cover_image_b64: Optional[str] = None
    if cover_image_path and Path(cover_image_path).exists():
        cover_image_b64 = base64.b64encode(Path(cover_image_path).read_bytes()).decode()
        _ok(f"Loaded cover image from {cover_image_path}")
    elif cover_image_path:
        _warn("File not found — cover will have no background image")

    # ── Executive summary ─────────────────────
    _header("Executive Summary")
    overview = _ask("Overview paragraph")
    results = _ask_list("Results (bullet points)")
    to_discuss = _ask_list("To be discussed items")

    # ── Decision Overview ─────────────────────
    _header("Decision Overview")
    decision_notebook = _ask_notebook("Decision Overview")
    decision_title = _ask("Slide title", default="Decision Overview")

    # ── Tier II ───────────────────────────────
    _header("Tier II")
    tier_notebook = _ask_notebook("Tier II")
    tier_title = _ask("Slide title", default="Tier II Analysis")

    # ── Risks, Limitations, Opportunities ─────
    _header("Risks, Limitations & Opportunities")
    risks_list = _ask_list("Risks")
    lim_list = _ask_list("Limitations")
    opp_list = _ask_list("Opportunities")

    # ── NPV Results ───────────────────────────
    _header("NPV Results")
    _sub("Query multiple model-type tables and plot NPV by AKI band.")
    npv_scenario = _ask("Scenario name filter", default="risk-worsening")
    npv_current = _ask("Current model table (blank to skip)", default="")
    npv_pclip = _ask("pClip table (blank to skip)", default="")
    npv_actuals = _ask("Actuals table (blank to skip)", default="")
    npv_sec = _ask("SEC table (blank to skip)", default="")
    npv_col_current = _ask("NPV column — current table", default="npv_with_mgm")
    npv_col_others = _ask("NPV column — other tables", default="npv")
    npv_bands_raw = _ask("AKI bands (comma-separated)", default="21,22,23,24,25,26,27,28,29,30")
    npv_bands = [int(b.strip()) for b in npv_bands_raw.split(",") if b.strip()]
    npv_chart = _ask("Chart type (line/bar)", default="line")
    npv_slide_title = _ask("Slide title", default="NPV by Aki Band · Risk Worsening Scenario")

    npv_cfg = NpvTablesConfig(
        current=npv_current or None,
        pclip=npv_pclip or None,
        actuals=npv_actuals or None,
        sec=npv_sec or None,
        npv_column_current=npv_col_current,
        npv_column_others=npv_col_others,
        scenario_filter=npv_scenario,
        aki_bands=npv_bands,
        chart_type=npv_chart,
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
    curves_source = _ask(
        "Source type (notebook / google-slides)",
        default="notebook",
    ).strip().lower()
    curves_notebook: Optional[NotebookRef] = None
    curves_google: Optional[GoogleSlidesRef] = None
    curves_google_token: str = ""
    curves_title = "Curves Overview"

    if curves_source.startswith("g"):
        curves_google, curves_google_token = _ask_google_slides("Curves Overview")
    else:
        curves_notebook = _ask_notebook("Curves Overview")
        curves_title = _ask("Slide title", default="Curves Overview")

    # ── Cohort Monitoring ─────────────────────
    _header("Cohort Monitoring")
    cohort_table = _ask("Table name (catalog.schema.table)")
    cohort_bands_raw = _ask("AKI bands (comma-separated)", default="21,22,23,24,25,26,27,28,29,30")
    cohort_bands = [int(b.strip()) for b in cohort_bands_raw.split(",") if b.strip()]
    cohort_max_month = _ask_int("Max month", default=12)

    console.print("  Legend renames:")
    legend_static = _ask("  Rename 'static' to", default="actuals")
    legend_running = _ask("  Rename 'running' to", default="pClip")
    legend_map = {"static": legend_static, "running": legend_running}

    all_metric_keys = [m for m, _ in COHORT_METRICS]
    console.print(f"  Available metrics: [dim]{', '.join(all_metric_keys)}[/dim]")
    cohort_metrics_raw = _ask(
        "Metrics to include (comma-sep, blank = all)",
        default="",
    )
    cohort_metrics = (
        [m.strip() for m in cohort_metrics_raw.split(",") if m.strip()]
        if cohort_metrics_raw.strip()
        else []
    )

    cohort_cfg = CohortMonitoringConfig(
        table=cohort_table,
        aki_bands=cohort_bands,
        legend_map=legend_map,
        metrics=cohort_metrics,
        max_month=cohort_max_month,
    )

    # ── Appendix ──────────────────────────────
    _header("Appendix")
    appendix_choice = _ask(
        "What to include? (google-slides / images / none)",
        default="none",
    ).strip().lower()
    appendix_google: Optional[GoogleSlidesRef] = None
    appendix_google_token: str = ""
    appendix_image_paths: list[str] = []

    if appendix_choice.startswith("g"):
        appendix_google, appendix_google_token = _ask_google_slides("Appendix")
    elif appendix_choice.startswith("i"):
        img_dir = _ask("Directory containing images (or comma-separated file paths)")
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

    # ── Build options ─────────────────────────
    _header("Build & Deploy")
    do_deploy = _ask_yn("Deploy to Databricks App after building?", default=False)
    app_name = ""
    if do_deploy:
        app_name = _ask("App name", default=f"{pres_name}-slides")

    # ── Save config ───────────────────────────
    cfg_dict = _build_config_dict(locals())
    if config_out:
        _save_config(cfg_dict, Path(config_out))
        _ok(f"Config saved to {config_out}")

    # ── Generate & assemble ───────────────────
    _header("Generating slides")
    slides = _generate_slides(client, cfg_dict, pres_name, pres_title, squad, date,
                               cover_image_b64, overview, results, to_discuss,
                               decision_notebook, decision_title,
                               tier_notebook, tier_title,
                               risks_list, lim_list, opp_list,
                               npv_cfg, npv_slide_title, npv_chart,
                               levers_notebook, levers_title,
                               iram_notebook, iram_title,
                               roa_notebook, roa_title,
                               curves_notebook, curves_google, curves_google_token, curves_title,
                               cohort_cfg,
                               appendix_google, appendix_google_token, appendix_image_paths,
                               appendix_choice)

    pres_dir = assemble(pres_name, slides, pres_title, slips_path / "presentations")
    _ok(f"Assembled {len(slides)} slides → {pres_dir}")

    # ── Build (node) ──────────────────────────
    _header("Building")
    try:
        built_html = build_presentation(pres_name, slips_path)
        _ok(f"Built: {built_html} ({built_html.stat().st_size / 1e6:.1f} MB)")
    except Exception as exc:
        _err(f"Build failed: {exc}")
        _warn("Check that Node.js and the slips CLI are installed.")
        sys.exit(1)

    # ── Deploy ────────────────────────────────
    if do_deploy:
        _header("Deploying")
        try:
            url = deploy(
                client=client,
                app_name=app_name,
                built_html=built_html,
                description=f"{pres_title} — decision slides",
                progress_callback=_ok,
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
# build from saved config
# ──────────────────────────────────────────────

@main.command("build")
@click.argument("config_file", type=click.Path(exists=True))
@click.option("--slips-root", type=click.Path(), default=None)
def build_cmd(config_file, slips_root):
    """Build presentation from a saved config YAML file (no prompts)."""
    slips_path = Path(slips_root) if slips_root else Path.home() / "slips"
    cfg = yaml.safe_load(Path(config_file).read_text(encoding="utf-8"))

    db_cfg = DatabricksConfig(**cfg["databricks"])
    client = DatabricksClient(db_cfg)

    _header("Building from config")
    slides = _generate_slides_from_dict(client, cfg)
    pres_dir = assemble(
        cfg["name"], slides, cfg["title"],
        slips_path / "presentations",
    )
    _ok(f"Assembled {len(slides)} slides → {pres_dir}")

    built_html = build_presentation(cfg["name"], slips_path)
    _ok(f"Built: {built_html} ({built_html.stat().st_size / 1e6:.1f} MB)")


# ──────────────────────────────────────────────
# deploy from saved config
# ──────────────────────────────────────────────

@main.command("deploy")
@click.argument("config_file", type=click.Path(exists=True))
@click.option("--slips-root", type=click.Path(), default=None)
def deploy_cmd(config_file, slips_root):
    """Deploy a built presentation (must have been built first)."""
    slips_path = Path(slips_root) if slips_root else Path.home() / "slips"
    cfg = yaml.safe_load(Path(config_file).read_text(encoding="utf-8"))

    db_cfg = DatabricksConfig(**cfg["databricks"])
    client = DatabricksClient(db_cfg)

    name = cfg["name"]
    built_html = slips_path / "presentations" / f"{name}.built.html"
    if not built_html.exists():
        _err(f"Built file not found: {built_html}. Run `decision-slides build` first.")
        sys.exit(1)

    app_name = cfg.get("app_name", f"{name}-slides")
    title = cfg.get("title", name)

    _header("Deploying")
    url = deploy(
        client=client,
        app_name=app_name,
        built_html=built_html,
        description=f"{title} — decision slides",
        progress_callback=_ok,
    )
    console.print()
    console.print(Panel(f"[bold green]Live at:[/bold green] {url}", border_style="green"))


# ──────────────────────────────────────────────
# slide generation logic (shared between new/build)
# ──────────────────────────────────────────────

def _generate_slides(
    client: DatabricksClient,
    cfg_dict: dict,
    pres_name: str,
    pres_title: str,
    squad: str,
    date: str,
    cover_image_b64: Optional[str],
    overview: str,
    results: list[str],
    to_discuss: list[str],
    decision_notebook: NotebookRef,
    decision_title: str,
    tier_notebook: NotebookRef,
    tier_title: str,
    risks_list: list[str],
    lim_list: list[str],
    opp_list: list[str],
    npv_cfg: NpvTablesConfig,
    npv_slide_title: str,
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

    # 1. Cover
    console.print("  [dim]→[/dim] Cover …")
    slides.append(("01-cover.html",
        gen_cover.generate(pres_title, squad, date, cover_image_b64)))

    # 2. Executive summary
    console.print("  [dim]→[/dim] Executive Summary …")
    slides.append(("02-executive-summary.html",
        gen_exec.generate(overview, results, to_discuss)))

    # 3. Decision overview
    console.print("  [dim]→[/dim] Decision Overview …")
    try:
        slides.append(("03-decision-overview.html",
            gen_decision.generate_from_notebook(client, decision_notebook, title=decision_title)))
        _ok("Decision Overview")
    except Exception as e:
        _warn(f"Decision Overview fetch failed ({e}) — placeholder inserted")
        slides.append(("03-decision-overview.html",
            _placeholder_slide("decision-overview", "Decision Overview", decision_title)))

    # 4. Tier II
    console.print("  [dim]→[/dim] Tier II …")
    try:
        slides.append(("04-tier-ii.html",
            gen_tier.generate_from_notebook(client, tier_notebook, title=tier_title)))
        _ok("Tier II")
    except Exception as e:
        _warn(f"Tier II fetch failed ({e}) — placeholder inserted")
        slides.append(("04-tier-ii.html",
            _placeholder_slide("tier-ii", "Tier II", tier_title)))

    # 5. Risks / Limitations / Opportunities
    console.print("  [dim]→[/dim] Risks …")
    slides.append(("05-risks-limitations-opportunities.html",
        gen_risks.generate(risks_list, lim_list, opp_list)))

    # 6. NPV Results
    console.print("  [dim]→[/dim] NPV Results …")
    try:
        npv_data = gen_npv.fetch_data(client, npv_cfg)
        slides.append(("06-npv-results.html",
            gen_npv.generate(npv_data, chart_type=npv_chart, title=npv_slide_title)))
        _ok("NPV Results")
    except Exception as e:
        _warn(f"NPV Results failed ({e}) — placeholder inserted")
        slides.append(("06-npv-results.html",
            _placeholder_slide("npv-results", "NPV Results", npv_slide_title)))

    # 7. NPV Levers
    console.print("  [dim]→[/dim] NPV Levers …")
    try:
        slides.append(("07-npv-levers.html",
            gen_levers.generate_from_notebook(client, levers_notebook, title=levers_title)))
        _ok("NPV Levers")
    except Exception as e:
        _warn(f"NPV Levers fetch failed ({e}) — placeholder inserted")
        slides.append(("07-npv-levers.html",
            _placeholder_slide("npv-levers", "NPV Levers", levers_title)))

    # 8. iRAM
    console.print("  [dim]→[/dim] iRAM …")
    try:
        slides.append(("08-iram.html",
            gen_iram.generate_from_notebook(client, iram_notebook, title=iram_title)))
        _ok("iRAM")
    except Exception as e:
        _warn(f"iRAM fetch failed ({e}) — placeholder inserted")
        slides.append(("08-iram.html",
            _placeholder_slide("iram", "iRAM", iram_title)))

    # 9. ROA
    console.print("  [dim]→[/dim] ROA …")
    try:
        slides.append(("09-roa.html",
            gen_roa.generate_from_notebook(client, roa_notebook, title=roa_title)))
        _ok("ROA")
    except Exception as e:
        _warn(f"ROA fetch failed ({e}) — placeholder inserted")
        slides.append(("09-roa.html",
            _placeholder_slide("roa", "ROA", roa_title)))

    # 10. Curves Overview
    console.print("  [dim]→[/dim] Curves Overview …")
    try:
        if curves_google:
            curve_slides = gen_curves.generate_from_google_slides(
                curves_google, curves_google_token,
            )
            for i, (fn, html) in enumerate(curve_slides, 1):
                slides.append((f"10-curves-{i:02d}.html", html))
        else:
            slides.append(("10-curves-overview.html",
                gen_curves.generate_from_notebook(client, curves_notebook, title=curves_title)))
        _ok("Curves Overview")
    except Exception as e:
        _warn(f"Curves Overview failed ({e}) — placeholder inserted")
        slides.append(("10-curves-overview.html",
            _placeholder_slide("curves-overview", "Curves Overview", curves_title)))

    # 11. Cohort Monitoring
    console.print("  [dim]→[/dim] Cohort Monitoring (fetching data) …")
    try:
        cohort_df = gen_cohort.fetch_data(client, cohort_cfg)
        cohort_slides = gen_cohort.generate_all(cohort_df, cohort_cfg, start_index=1)
        for i, (fn, html) in enumerate(cohort_slides):
            slides.append((f"11-cohort-{i + 1:02d}-{fn}", html))
        _ok(f"Cohort Monitoring ({len(cohort_slides)} metrics)")
    except Exception as e:
        _warn(f"Cohort Monitoring failed ({e}) — placeholder inserted")
        slides.append(("11-cohort-monitoring.html",
            _placeholder_slide("cohort-monitoring", "Cohort Monitoring", "Cohort Monitoring")))

    # 12. Appendix
    if not appendix_choice.startswith("n"):
        console.print("  [dim]→[/dim] Appendix …")
        slides.append(gen_appendix.section_header())
        try:
            if appendix_google:
                appendix_slides = gen_appendix.from_google_slides(
                    appendix_google.presentation_id(), appendix_google_token,
                )
                slides.extend(appendix_slides)
                _ok(f"Appendix ({len(appendix_slides)} slides from Google Slides)")
            elif appendix_image_paths:
                appendix_slides = gen_appendix.from_image_paths(appendix_image_paths)
                slides.extend(appendix_slides)
                _ok(f"Appendix ({len(appendix_slides)} images)")
        except Exception as e:
            _warn(f"Appendix failed ({e})")

    return slides


def _generate_slides_from_dict(client: DatabricksClient, cfg: dict) -> list[tuple[str, str]]:
    """Reconstruct all slide references from a saved YAML config dict."""

    def _nb(d: dict) -> NotebookRef:
        return NotebookRef(**d)

    def _gs(d: dict) -> GoogleSlidesRef:
        return GoogleSlidesRef(**d)

    npv = cfg.get("npv_results", {})
    npv_cfg = NpvTablesConfig(
        current=npv.get("current"),
        pclip=npv.get("pclip"),
        actuals=npv.get("actuals"),
        sec=npv.get("sec"),
        npv_column_current=npv.get("npv_column_current", "npv_with_mgm"),
        npv_column_others=npv.get("npv_column_others", "npv"),
        scenario_filter=npv.get("scenario_filter", "risk-worsening"),
        aki_bands=npv.get("aki_bands", list(range(21, 31))),
        chart_type=npv.get("chart_type", "line"),
    )

    cm = cfg.get("cohort_monitoring", {})
    cohort_cfg = CohortMonitoringConfig(
        table=cm["table"],
        aki_bands=cm.get("aki_bands", list(range(21, 31))),
        legend_map=cm.get("legend_map", {}),
        metrics=cm.get("metrics", []),
        max_month=cm.get("max_month", 12),
    )

    curves_nb = _nb(cfg["curves_overview"]["notebook"]) if cfg.get("curves_overview", {}).get("notebook") else None
    curves_gs = _gs(cfg["curves_overview"]["google_slides"]) if cfg.get("curves_overview", {}).get("google_slides") else None

    ap = cfg.get("appendix", {})
    app_gs = _gs(ap["google_slides"]) if ap.get("google_slides") else None

    cover_image_b64 = None
    if cfg.get("cover_image_path"):
        p = Path(cfg["cover_image_path"])
        if p.exists():
            cover_image_b64 = base64.b64encode(p.read_bytes()).decode()

    return _generate_slides(
        client=client,
        cfg_dict=cfg,
        pres_name=cfg["name"],
        pres_title=cfg["title"],
        squad=cfg["squad"],
        date=cfg["date"],
        cover_image_b64=cover_image_b64,
        overview=cfg.get("executive_summary", {}).get("overview", ""),
        results=cfg.get("executive_summary", {}).get("results", []),
        to_discuss=cfg.get("executive_summary", {}).get("to_discuss", []),
        decision_notebook=_nb(cfg["decision_overview"]["notebook"]),
        decision_title=cfg["decision_overview"].get("title", "Decision Overview"),
        tier_notebook=_nb(cfg["tier_ii"]["notebook"]),
        tier_title=cfg["tier_ii"].get("title", "Tier II Analysis"),
        risks_list=cfg.get("risks_limitations_opportunities", {}).get("risks", []),
        lim_list=cfg.get("risks_limitations_opportunities", {}).get("limitations", []),
        opp_list=cfg.get("risks_limitations_opportunities", {}).get("opportunities", []),
        npv_cfg=npv_cfg,
        npv_slide_title=npv.get("title", "NPV by Aki Band · Risk Worsening Scenario"),
        npv_chart=npv.get("chart_type", "line"),
        levers_notebook=_nb(cfg["npv_levers"]["notebook"]),
        levers_title=cfg["npv_levers"].get("title", "NPV Levers"),
        iram_notebook=_nb(cfg["iram"]["notebook"]),
        iram_title=cfg["iram"].get("title", "iRAM Analysis"),
        roa_notebook=_nb(cfg["roa"]["notebook"]),
        roa_title=cfg["roa"].get("title", "ROA Analysis"),
        curves_notebook=curves_nb,
        curves_google=curves_gs,
        curves_google_token=cfg.get("curves_overview", {}).get("google_token", ""),
        curves_title=cfg.get("curves_overview", {}).get("title", "Curves Overview"),
        cohort_cfg=cohort_cfg,
        appendix_google=app_gs,
        appendix_google_token=ap.get("google_token", ""),
        appendix_image_paths=ap.get("image_paths", []),
        appendix_choice=ap.get("type", "none"),
    )


def _build_config_dict(ctx: dict) -> dict:
    """Build a serialisable config dict from wizard local variables."""
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
            "overview": ctx["overview"],
            "results": ctx["results"],
            "to_discuss": ctx["to_discuss"],
        },
        "decision_overview": {
            "notebook": {
                "notebook_url": ctx["decision_notebook"].notebook_url,
                "command_number": ctx["decision_notebook"].command_number,
            },
            "title": ctx["decision_title"],
        },
        "tier_ii": {
            "notebook": {
                "notebook_url": ctx["tier_notebook"].notebook_url,
                "command_number": ctx["tier_notebook"].command_number,
            },
            "title": ctx["tier_title"],
        },
        "risks_limitations_opportunities": {
            "risks": ctx["risks_list"],
            "limitations": ctx["lim_list"],
            "opportunities": ctx["opp_list"],
        },
        "npv_results": {
            "scenario_filter": ctx["npv_scenario"],
            "current": ctx["npv_current"] or None,
            "pclip": ctx["npv_pclip"] or None,
            "actuals": ctx["npv_actuals"] or None,
            "sec": ctx["npv_sec"] or None,
            "npv_column_current": ctx["npv_col_current"],
            "npv_column_others": ctx["npv_col_others"],
            "aki_bands": ctx["npv_bands"],
            "chart_type": ctx["npv_chart"],
            "title": ctx["npv_slide_title"],
        },
        "npv_levers": {
            "notebook": {
                "notebook_url": ctx["levers_notebook"].notebook_url,
                "command_number": ctx["levers_notebook"].command_number,
            },
            "title": ctx["levers_title"],
        },
        "iram": {
            "notebook": {
                "notebook_url": ctx["iram_notebook"].notebook_url,
                "command_number": ctx["iram_notebook"].command_number,
            },
            "title": ctx["iram_title"],
        },
        "roa": {
            "notebook": {
                "notebook_url": ctx["roa_notebook"].notebook_url,
                "command_number": ctx["roa_notebook"].command_number,
            },
            "title": ctx["roa_title"],
        },
        "curves_overview": {
            "notebook": (
                {
                    "notebook_url": ctx["curves_notebook"].notebook_url,
                    "command_number": ctx["curves_notebook"].command_number,
                }
                if ctx["curves_notebook"]
                else None
            ),
            "google_slides": (
                {"presentation_url": ctx["curves_google"].presentation_url}
                if ctx["curves_google"]
                else None
            ),
            "google_token": ctx["curves_google_token"],
            "title": ctx["curves_title"],
        },
        "cohort_monitoring": {
            "table": ctx["cohort_table"],
            "aki_bands": ctx["cohort_bands"],
            "max_month": ctx["cohort_max_month"],
            "legend_map": ctx["legend_map"],
            "metrics": ctx["cohort_metrics"],
        },
        "appendix": {
            "type": ctx["appendix_choice"],
            "google_slides": (
                {"presentation_url": ctx["appendix_google"].presentation_url}
                if ctx["appendix_google"]
                else None
            ),
            "google_token": ctx["appendix_google_token"],
            "image_paths": ctx["appendix_image_paths"],
        },
        "app_name": ctx["app_name"],
    }


def _placeholder_slide(slide_id: str, section_label: str, title: str) -> str:
    from .generators.base import BRAND_PURPLE
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

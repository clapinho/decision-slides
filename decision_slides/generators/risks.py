"""Risks, Limitations and Opportunities slide generator."""

from __future__ import annotations

from .base import BRAND_PURPLE


def generate(
    risks: list[str],
    limitations: list[str],
    opportunities: list[str],
    brand_color: str = BRAND_PURPLE,
) -> str:
    def _items(lst: list[str], icon: str) -> str:
        return "\n".join(
            f'        <li><span class="rlo-icon">{icon}</span><span>{item}</span></li>'
            for item in lst
        )

    risks_li = _items(risks, "⚠")
    lim_li = _items(limitations, "·")
    opp_li = _items(opportunities, "↑")

    risks_block = f"""
    <div class="rlo-col">
      <div class="rlo-col-title risk">Risks</div>
      <ul class="rlo-list">
{risks_li}
      </ul>
    </div>""" if risks else ""

    lim_block = f"""
    <div class="rlo-col">
      <div class="rlo-col-title lim">Limitations</div>
      <ul class="rlo-list">
{lim_li}
      </ul>
    </div>""" if limitations else ""

    opp_block = f"""
    <div class="rlo-col">
      <div class="rlo-col-title opp">Opportunities</div>
      <ul class="rlo-list">
{opp_li}
      </ul>
    </div>""" if opportunities else ""

    return f"""<slip-slide id="risks-limitations-opportunities" transition="fade">
  <style>
    .rlo-root {{
      height: 100%;
      background: #ffffff;
      color: #111827;
      font-family: var(--slip-font);
      display: flex;
      flex-direction: column;
      padding: 2rem 3.5rem;
    }}
    .rlo-tag {{ font-size: 0.7rem; font-weight: 500; color: #9ca3af; letter-spacing: 0.04em; margin-bottom: 0.4rem; }}
    .rlo-title {{ font-size: 1.8rem; font-weight: 700; color: {brand_color}; margin: 0 0 1.2rem; line-height: 1.1; }}
    .rlo-grid {{ display: flex; gap: 2rem; flex: 1; }}
    .rlo-col {{ flex: 1; }}
    .rlo-col-title {{
      font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
      text-transform: uppercase; margin-bottom: 0.6rem; padding-bottom: 0.4rem;
      border-bottom: 2px solid currentColor;
    }}
    .rlo-col-title.risk {{ color: #ef4444; }}
    .rlo-col-title.lim {{ color: #f59e0b; }}
    .rlo-col-title.opp {{ color: #10b981; }}
    .rlo-list {{ list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.45rem; }}
    .rlo-list li {{ display: flex; gap: 0.5rem; font-size: 0.8rem; color: #374151; line-height: 1.5; }}
    .rlo-icon {{ flex-shrink: 0; font-size: 0.8rem; margin-top: 0.1rem; }}
  </style>
  <div class="rlo-root">
    <div class="rlo-tag">Model Governance</div>
    <h2 class="rlo-title">Risks, Limitations &amp; Opportunities</h2>
    <div class="rlo-grid">
{risks_block}
{lim_block}
{opp_block}
    </div>
  </div>
</slip-slide>
"""

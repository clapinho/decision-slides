"""Base helpers shared by all slide generators."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


BRAND_PURPLE = "#820AD1"


def slide_html(
    slide_id: str,
    section_label: str,
    title: str,
    body_html: str,
    notes: str = "",
    transition: str = "fade",
    extra_css: str = "",
) -> str:
    """Render a generic slip-slide fragment."""
    notes_tag = f"\n  <slip-notes>{notes}</slip-notes>" if notes else ""
    return f"""<slip-slide id="{slide_id}" transition="{transition}">
  <style>
    .sl-root {{
      height: 100%;
      background: #ffffff;
      color: #111827;
      font-family: var(--slip-font);
      display: flex;
      flex-direction: column;
      padding: 1.6rem 3rem 1.2rem;
    }}
    .sl-header {{
      display: flex;
      align-items: baseline;
      gap: 0.8rem;
      margin-bottom: 1rem;
      border-bottom: 1px solid #e5e7eb;
      padding-bottom: 0.7rem;
      flex-shrink: 0;
    }}
    .sl-section {{
      font-size: 0.7rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: {BRAND_PURPLE};
    }}
    .sl-title {{
      font-size: 1.3rem;
      font-weight: 700;
      color: #111827;
      margin: 0;
    }}
    .sl-body {{
      flex: 1;
      min-height: 0;
      overflow: hidden;
    }}
    {extra_css}
  </style>
  <div class="sl-root">
    <div class="sl-header">
      <span class="sl-section">{section_label}</span>
      <h2 class="sl-title">{title}</h2>
    </div>
    <div class="sl-body">
{body_html}
    </div>
  </div>{notes_tag}
</slip-slide>
"""


def image_slide(
    slide_id: str,
    section_label: str,
    title: str,
    b64: str,
    alt: str = "",
    notes: str = "",
) -> str:
    """Slide with a single full-body image."""
    body = f'      <img style="width:100%;height:100%;object-fit:contain;object-position:center" src="data:image/png;base64,{b64}" alt="{alt}" />'
    return slide_html(slide_id, section_label, title, body, notes=notes,
                      extra_css=".sl-body { display:flex; align-items:center; justify-content:center; }")

"""Cover slide generator."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base import BRAND_PURPLE


def generate(
    title: str,
    squad: str,
    date: str,
    image_b64: Optional[str] = None,
    brand_color: str = BRAND_PURPLE,
) -> str:
    if image_b64:
        bg = f'<img class="cv-bg" src="data:image/png;base64,{image_b64}" alt="cover" />'
    else:
        bg = ""

    return f"""<slip-slide id="cover" transition="fade">
  <style>
    .cv-root {{
      height: 100%;
      background: linear-gradient(135deg, {brand_color}18 0%, #ffffff 60%);
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      justify-content: center;
      padding: 3rem 4rem;
      position: relative;
      overflow: hidden;
    }}
    .cv-bg {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      opacity: 0.08;
      z-index: 0;
    }}
    .cv-content {{ position: relative; z-index: 1; }}
    .cv-squad {{
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: {brand_color};
      margin-bottom: 0.5rem;
    }}
    .cv-title {{
      font-size: 2.8rem;
      font-weight: 800;
      color: #111827;
      line-height: 1.1;
      margin: 0 0 1.2rem;
    }}
    .cv-date {{
      font-size: 0.85rem;
      color: #6b7280;
    }}
    .cv-bar {{
      width: 4rem;
      height: 0.3rem;
      background: {brand_color};
      border-radius: 2px;
      margin-bottom: 1.2rem;
    }}
  </style>
  <div class="cv-root">
    {bg}
    <div class="cv-content">
      <div class="cv-squad">{squad}</div>
      <div class="cv-title">{title}</div>
      <div class="cv-bar"></div>
      <div class="cv-date">{date}</div>
    </div>
  </div>
</slip-slide>
"""

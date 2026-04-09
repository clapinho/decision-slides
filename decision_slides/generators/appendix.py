"""Appendix slide generators — Google Slides thumbnails or images."""

from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from typing import Optional

import requests

from .base import image_slide


def from_google_slides(
    presentation_id: str,
    google_token: str,
    start_index: int = 1,
) -> list[tuple[str, str]]:
    """
    Download all slide thumbnails from a Google Slides presentation.
    Requires a valid Google OAuth access token with drive.readonly scope.
    Returns list of (filename, html) pairs.
    """
    # List slides
    resp = requests.get(
        f"https://slides.googleapis.com/v1/presentations/{presentation_id}",
        headers={"Authorization": f"Bearer {google_token}"},
    )
    resp.raise_for_status()
    presentation = resp.json()
    slide_ids = [s["objectId"] for s in presentation.get("slides", [])]

    slides = []
    for i, slide_id in enumerate(slide_ids):
        # Get thumbnail URL
        thumb_resp = requests.get(
            f"https://slides.googleapis.com/v1/presentations/{presentation_id}/pages/{slide_id}/thumbnail",
            headers={"Authorization": f"Bearer {google_token}"},
            params={"thumbnailProperties.thumbnailSize": "LARGE"},
        )
        thumb_resp.raise_for_status()
        thumb_url = thumb_resp.json()["contentUrl"]

        # Download thumbnail
        img_resp = requests.get(thumb_url)
        img_resp.raise_for_status()
        b64 = base64.b64encode(img_resp.content).decode()

        slide_num = start_index + i
        html = image_slide(
            slide_id=f"appendix-curves-{slide_num:02d}",
            section_label="Appendix",
            title=f"Curves Construction · {slide_num}/{len(slide_ids)}",
            b64=b64,
            alt=f"Appendix slide {slide_num}",
        )
        filename = f"appendix-curves-{slide_num:02d}.html"
        slides.append((filename, html))

    return slides


def from_image_paths(
    image_paths: list[str],
    section_label: str = "Appendix",
    start_index: int = 1,
) -> list[tuple[str, str]]:
    """Create appendix slides from local image files."""
    slides = []
    total = len(image_paths)
    for i, path in enumerate(sorted(image_paths)):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        slide_num = start_index + i
        name = Path(path).stem
        html = image_slide(
            slide_id=f"appendix-{slide_num:02d}",
            section_label=section_label,
            title=f"Appendix · {name}",
            b64=b64,
            alt=name,
        )
        filename = f"appendix-{slide_num:02d}.html"
        slides.append((filename, html))
    return slides


def section_header(label: str = "Appendix") -> tuple[str, str]:
    """A simple section divider slide for the appendix."""
    html = f"""<slip-slide id="appendix-header" transition="fade">
  <style>
    .ah-root {{
      height: 100%;
      background: #ffffff;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .ah-label {{
      font-size: 3rem;
      font-weight: 800;
      color: #e5e7eb;
      letter-spacing: 0.05em;
    }}
  </style>
  <div class="ah-root">
    <div class="ah-label">{label}</div>
  </div>
</slip-slide>
"""
    return ("appendix-header.html", html)

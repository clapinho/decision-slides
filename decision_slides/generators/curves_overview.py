"""Curves Overview slide generator — notebook image or Google Slides pages."""

from __future__ import annotations

import base64

from .base import image_slide, BRAND_PURPLE
from ..config import NotebookRef, GoogleSlidesRef


def generate_from_image(
    img_bytes: bytes,
    title: str = "Curves Overview",
    brand_color: str = BRAND_PURPLE,
) -> str:
    b64 = base64.b64encode(img_bytes).decode()
    return image_slide(
        slide_id="curves-overview",
        section_label="Curves Overview",
        title=title,
        b64=b64,
        alt="Curves Overview",
    )


def generate_from_notebook(
    client,
    notebook_ref: NotebookRef,
    title: str = "Curves Overview",
    brand_color: str = BRAND_PURPLE,
) -> str:
    img_bytes = client.get_notebook_command_output(
        notebook_ref.notebook_id(),
        notebook_ref.command_number,
    )
    return generate_from_image(img_bytes, title=title, brand_color=brand_color)


def generate_from_google_slides(
    google_ref: GoogleSlidesRef,
    google_token: str,
    start_index: int = 1,
    title_prefix: str = "Curves Overview",
    section_label: str = "Curves Overview",
) -> list[tuple[str, str]]:
    """
    Download all thumbnails from a Google Slides presentation and create one
    slide per page. Requires a valid Google OAuth access token with
    drive.readonly scope.
    Returns a list of (filename, html) pairs.
    """
    import requests

    presentation_id = google_ref.presentation_id()
    resp = requests.get(
        f"https://slides.googleapis.com/v1/presentations/{presentation_id}",
        headers={"Authorization": f"Bearer {google_token}"},
    )
    resp.raise_for_status()
    slide_ids = [s["objectId"] for s in resp.json().get("slides", [])]

    slides = []
    total = len(slide_ids)
    for i, slide_id in enumerate(slide_ids):
        thumb_resp = requests.get(
            f"https://slides.googleapis.com/v1/presentations/{presentation_id}/pages/{slide_id}/thumbnail",
            headers={"Authorization": f"Bearer {google_token}"},
            params={"thumbnailProperties.thumbnailSize": "LARGE"},
        )
        thumb_resp.raise_for_status()
        thumb_url = thumb_resp.json()["contentUrl"]

        img_resp = requests.get(thumb_url)
        img_resp.raise_for_status()
        b64 = base64.b64encode(img_resp.content).decode()

        slide_num = start_index + i
        html = image_slide(
            slide_id=f"curves-overview-{slide_num:02d}",
            section_label=section_label,
            title=f"{title_prefix} · {slide_num}/{total}",
            b64=b64,
            alt=f"Curves overview slide {slide_num}",
        )
        filename = f"curves-overview-{slide_num:02d}.html"
        slides.append((filename, html))

    return slides

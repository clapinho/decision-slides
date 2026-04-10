"""Tier II slide generator."""

from __future__ import annotations

import base64

from .base import image_slide, BRAND_PURPLE
from ..config import NotebookRef

SLIDE_ID = "tier-ii"


def generate_from_image(
    img_bytes: bytes,
    title: str = "Tier II Analysis",
    brand_color: str = BRAND_PURPLE,
    ctx=None,
) -> str:
    if ctx:
        ctx.save_notebook_image(SLIDE_ID, img_bytes)
    b64 = base64.b64encode(img_bytes).decode()
    return image_slide(
        slide_id=SLIDE_ID,
        section_label="Tier II",
        title=title,
        b64=b64,
        alt="Tier II",
    )


def generate_from_notebook(
    client,
    notebook_ref: NotebookRef,
    title: str = "Tier II Analysis",
    brand_color: str = BRAND_PURPLE,
    ctx=None,
) -> str:
    img_bytes = client.get_notebook_command_output(
        notebook_ref.notebook_id(),
        notebook_ref.command_number,
    )
    return generate_from_image(img_bytes, title=title, brand_color=brand_color, ctx=ctx)

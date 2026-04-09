"""
Assembles a slips presentation folder from generated slide HTML files.

Output structure:
  presentations/{name}/
    slides.json          — ordered list of slide filenames
    index.html           — slips entry point
    01-cover.html
    02-executive-summary.html
    …
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from importlib import resources


SLIPS_INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <script src="../../packages/slipshow/dist/slipshow.bundled.js"></script>
  <style>
    body {{ margin: 0; background: #1f2937; }}
    slip-slipshow {{ --slip-font: 'Inter', system-ui, sans-serif; }}
  </style>
</head>
<body>
<slip-slipshow>
{slides_include}
</slip-slipshow>
<script>
  SlipShow.setupAll();
</script>
</body>
</html>
"""


def assemble(
    name: str,
    slides: list[tuple[str, str]],
    title: str,
    presentations_root: Path | None = None,
) -> Path:
    """
    Write all slide HTML files and slides.json to the presentation folder.
    Returns the path to the presentation folder.

    Args:
        name: Presentation folder name (e.g. "mx-valuation")
        slides: List of (filename, html_content) pairs in presentation order
        title: Human-readable title for index.html
        presentations_root: Root folder containing presentations (default: ~/slips/presentations)
    """
    if presentations_root is None:
        presentations_root = Path.home() / "slips" / "presentations"

    pres_dir = presentations_root / name
    pres_dir.mkdir(parents=True, exist_ok=True)

    filenames = []
    for filename, html in slides:
        out_path = pres_dir / filename
        out_path.write_text(html, encoding="utf-8")
        filenames.append(filename)

    # slides.json
    slides_json = pres_dir / "slides.json"
    slides_json.write_text(json.dumps(filenames, indent=2) + "\n", encoding="utf-8")

    # index.html
    includes = "\n".join(
        f'  <slip-slide src="{fn}"></slip-slide>' for fn in filenames
    )
    index_html = SLIPS_INDEX_TEMPLATE.format(title=title, slides_include=includes)
    (pres_dir / "index.html").write_text(index_html, encoding="utf-8")

    return pres_dir

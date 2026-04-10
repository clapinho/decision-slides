"""
ContextStore — saves all raw slide inputs to presentations/{name}/context/
so they can be inspected or reused in future sessions without re-fetching.

Saved files:
  context/manifest.json          — index of all saved artifacts
  context/notebook_{id}.png      — PNG image fetched from a notebook cell
  context/npv_results.json       — NPV data dict
  context/cohort_monitoring.csv  — cohort monitoring DataFrame
  context/executive_summary.json — executive summary text
  context/risks.json             — risks / limitations / opportunities text
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Optional


class ContextStore:
    def __init__(self, presentation_dir: Path):
        self.dir = presentation_dir / "context"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._manifest: dict[str, Any] = {}
        manifest_path = self.dir / "manifest.json"
        if manifest_path.exists():
            try:
                self._manifest = json.loads(manifest_path.read_text())
            except Exception:
                pass

    def _save_manifest(self):
        (self.dir / "manifest.json").write_text(
            json.dumps(self._manifest, indent=2), encoding="utf-8"
        )

    # ── Notebook images ───────────────────────────────────────────────────────

    def save_notebook_image(self, slide_id: str, img_bytes: bytes,
                            notebook_id: Optional[str] = None,
                            command_number: Optional[int] = None) -> Path:
        filename = f"notebook_{slide_id}.png"
        path = self.dir / filename
        path.write_bytes(img_bytes)
        self._manifest[slide_id] = {
            "type": "notebook_image",
            "file": filename,
            "notebook_id": notebook_id,
            "command_number": command_number,
        }
        self._save_manifest()
        return path

    def load_notebook_image(self, slide_id: str) -> Optional[bytes]:
        entry = self._manifest.get(slide_id)
        if entry and entry.get("type") == "notebook_image":
            path = self.dir / entry["file"]
            if path.exists():
                return path.read_bytes()
        return None

    # ── SQL / DataFrame data ──────────────────────────────────────────────────

    def save_dataframe(self, key: str, df, sql: Optional[str] = None) -> Path:
        """Save a pandas DataFrame as CSV."""
        filename = f"{key}.csv"
        path = self.dir / filename
        df.to_csv(path, index=False)
        self._manifest[key] = {
            "type": "dataframe",
            "file": filename,
            "sql": sql,
        }
        self._save_manifest()
        return path

    def load_dataframe(self, key: str):
        """Load a saved DataFrame. Returns None if not found."""
        import pandas as pd
        entry = self._manifest.get(key)
        if entry and entry.get("type") == "dataframe":
            path = self.dir / entry["file"]
            if path.exists():
                return pd.read_csv(path)
        return None

    def save_npv_data(self, data: dict, sql: Optional[str] = None) -> Path:
        filename = "npv_results.json"
        path = self.dir / filename
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._manifest["npv_results"] = {
            "type": "npv_data",
            "file": filename,
            "sql": sql,
        }
        self._save_manifest()
        return path

    def load_npv_data(self) -> Optional[dict]:
        entry = self._manifest.get("npv_results")
        if entry and entry.get("type") == "npv_data":
            path = self.dir / entry["file"]
            if path.exists():
                return json.loads(path.read_text())
        return None

    # ── Text content ──────────────────────────────────────────────────────────

    def save_text(self, key: str, data: dict) -> Path:
        filename = f"{key}.json"
        path = self.dir / filename
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        self._manifest[key] = {"type": "text", "file": filename}
        self._save_manifest()
        return path

    def load_text(self, key: str) -> Optional[dict]:
        entry = self._manifest.get(key)
        if entry and entry.get("type") == "text":
            path = self.dir / entry["file"]
            if path.exists():
                return json.loads(path.read_text())
        return None

    # ── Summary ───────────────────────────────────────────────────────────────

    def summary(self) -> str:
        lines = [f"Context saved in: {self.dir}", ""]
        for key, entry in self._manifest.items():
            ftype = entry.get("type", "?")
            fname = entry.get("file", "?")
            lines.append(f"  {key:35s}  [{ftype}]  {fname}")
        return "\n".join(lines)

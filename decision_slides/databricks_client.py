"""Databricks REST API client — SQL queries, notebook commands, DBFS reads."""

from __future__ import annotations

import base64
import re
import time
from typing import Any, Optional, Union

import requests


class DatabricksClient:
    def __init__(self, config_or_url, token: str = "", warehouse_id: str = ""):
        """
        Can be constructed two ways:
          DatabricksClient(DatabricksConfig(...))
          DatabricksClient(workspace_url, token, warehouse_id)
        """
        from .config import DatabricksConfig  # local import to avoid circular
        if isinstance(config_or_url, DatabricksConfig):
            cfg = config_or_url
            self.base = cfg.workspace_url.rstrip("/")
            self.token = cfg.token
            self.warehouse_id = cfg.warehouse_id
        else:
            self.base = config_or_url.rstrip("/")
            self.token = token
            self.warehouse_id = warehouse_id
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    # ── SQL ──────────────────────────────────────────────────────────────────

    def query(self, sql: str, timeout_seconds: int = 120) -> list[dict]:
        """Execute SQL on the configured SQL warehouse. Returns list of row dicts."""
        resp = self._post("/api/2.0/sql/statements", {
            "warehouse_id": self.warehouse_id,
            "statement": sql,
            "wait_timeout": f"{timeout_seconds}s",
            "on_wait_timeout": "WAIT",
        })
        state = resp.get("status", {}).get("state", "UNKNOWN")
        stmt_id = resp.get("statement_id", "")

        # Poll if still running
        deadline = time.time() + timeout_seconds
        while state not in ("SUCCEEDED", "FAILED", "CANCELED", "CLOSED"):
            if time.time() > deadline:
                raise TimeoutError(f"SQL statement {stmt_id} timed out")
            time.sleep(2)
            resp = self._get(f"/api/2.0/sql/statements/{stmt_id}")
            state = resp.get("status", {}).get("state", "UNKNOWN")

        if state != "SUCCEEDED":
            raise RuntimeError(f"SQL failed ({state}): {resp.get('status', {}).get('error', {})}")

        schema = resp["manifest"]["schema"]["columns"]
        col_names = [c["name"] for c in schema]
        rows = []
        for row in resp.get("result", {}).get("data_array", []):
            if isinstance(row, dict):
                # {values: [{string_value: ...}, ...]} format
                values = [v.get("string_value") for v in row.get("values", [])]
            else:
                values = row
            rows.append(dict(zip(col_names, values)))
        return rows

    def query_as_df(self, sql: str):
        """Query and return a pandas DataFrame."""
        import pandas as pd
        rows = self.query(sql)
        return pd.DataFrame(rows)

    # ── Notebook commands ────────────────────────────────────────────────────

    def get_notebook_command_output(self, notebook_id: str, command_index: int) -> bytes:
        """
        Export a notebook, find the code cell at command_index (1-based), and return
        the first PNG image output as raw bytes. Raises if no image output is found.
        """
        import json

        path = self._resolve_notebook_path(notebook_id)
        resp = self._get("/api/2.0/workspace/export", params={
            "path": path,
            "format": "JUPYTER",
        })
        content_b64 = resp.get("content", "")
        nb = json.loads(base64.b64decode(content_b64).decode("utf-8"))
        cells = nb.get("cells", [])
        code_cells = [c for c in cells if c.get("cell_type") == "code"]
        if command_index < 1 or command_index > len(code_cells):
            raise IndexError(
                f"Command {command_index} out of range "
                f"(notebook has {len(code_cells)} code cells)"
            )
        outputs = code_cells[command_index - 1].get("outputs", [])
        for out in outputs:
            data = out.get("data", {})
            for mime in ("image/png", "image/jpeg", "image/gif"):
                if mime in data:
                    return base64.b64decode(data[mime])
        raise ValueError(
            f"No image output found in cell {command_index}. "
            "Make sure the cell displays a matplotlib / plotly figure."
        )

    def _resolve_notebook_path(self, notebook_id: str) -> str:
        """Get workspace path for a notebook ID (numeric string)."""
        try:
            resp = self._get(
                "/api/2.0/workspace/get-status",
                params={"object_id": int(notebook_id)},
            )
            if "path" in resp:
                return resp["path"]
        except Exception:
            pass
        raise ValueError(
            f"Cannot resolve notebook ID {notebook_id!r}. "
            "Provide the full /Users/… workspace path instead."
        )

    # ── DBFS ─────────────────────────────────────────────────────────────────

    def read_dbfs_file(self, dbfs_path: str) -> bytes:
        """Read a file from DBFS (chunked)."""
        chunks = []
        offset = 0
        chunk_size = 1_000_000  # 1 MB
        while True:
            resp = self._get("/api/2.0/dbfs/read", params={
                "path": dbfs_path,
                "offset": offset,
                "length": chunk_size,
            })
            data = base64.b64decode(resp["data"])
            chunks.append(data)
            if resp["bytes_read"] < chunk_size:
                break
            offset += resp["bytes_read"]
        return b"".join(chunks)

    def write_dbfs_file(self, dbfs_path: str, data: bytes, overwrite: bool = True) -> None:
        """Write a file to DBFS using chunked upload."""
        resp = self._post("/api/2.0/dbfs/create", {"path": dbfs_path, "overwrite": overwrite})
        handle = resp["handle"]
        chunk_size = 1_000_000
        for i in range(0, len(data), chunk_size):
            self._post("/api/2.0/dbfs/add-block", {
                "handle": handle,
                "data": base64.b64encode(data[i:i + chunk_size]).decode(),
            })
        self._post("/api/2.0/dbfs/close", {"handle": handle})

    # ── Workspace files ───────────────────────────────────────────────────────

    def upload_workspace_file(self, ws_path: str, content: bytes, overwrite: bool = True) -> None:
        """Upload a file (not notebook) to the workspace."""
        # Try to delete first if overwriting (handles type-mismatch errors)
        if overwrite:
            try:
                self._post("/api/2.0/workspace/delete", {"path": ws_path, "recursive": False})
            except Exception:
                pass
        self._post("/api/2.0/workspace/import", {
            "path": ws_path,
            "content": base64.b64encode(content).decode(),
            "format": "AUTO",
            "overwrite": False,
        })

    def mkdirs(self, ws_path: str) -> None:
        self._post("/api/2.0/workspace/mkdirs", {"path": ws_path})

    # ── Apps ─────────────────────────────────────────────────────────────────

    def create_or_get_app(self, name: str, description: str = "") -> dict:
        resp = self._post("/api/2.0/apps", {"name": name, "description": description})
        return resp

    def deploy_app(self, app_name: str, source_path: str) -> str:
        """Deploy an app. Returns deployment_id."""
        resp = self._post(f"/api/2.0/apps/{app_name}/deployments", {
            "source_code_path": source_path,
            "mode": "SNAPSHOT",
        })
        return resp.get("deployment_id", "")

    def wait_for_app(self, app_name: str, timeout: int = 300) -> dict:
        """Wait for app compute to be ACTIVE."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            app = self._get(f"/api/2.0/apps/{app_name}")
            state = app.get("compute_status", {}).get("state", "")
            if state == "ACTIVE":
                return app
            time.sleep(10)
        raise TimeoutError(f"App {app_name} did not become ACTIVE in {timeout}s")

    def wait_for_deployment(self, app_name: str, dep_id: str, timeout: int = 120) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            dep = self._get(f"/api/2.0/apps/{app_name}/deployments/{dep_id}")
            state = dep.get("status", {}).get("state", "?")
            if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
                return dep
            time.sleep(10)
        raise TimeoutError(f"Deployment {dep_id} timed out")

    def set_app_permissions(self, app_name: str, level: str = "CAN_USE") -> None:
        """Grant all workspace users the given permission level on an app."""
        self._put(f"/api/2.0/permissions/apps/{app_name}", {
            "access_control_list": [
                {"group_name": "users", "permission_level": level}
            ]
        })

    # ── Internal ─────────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict | None = None) -> dict:
        r = requests.get(f"{self.base}{path}", headers=self._headers, params=params)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        r = requests.post(f"{self.base}{path}", headers=self._headers, json=body)
        r.raise_for_status()
        return r.json()

    def _put(self, path: str, body: dict) -> dict:
        r = requests.put(f"{self.base}{path}", headers=self._headers, json=body)
        r.raise_for_status()
        return r.json()

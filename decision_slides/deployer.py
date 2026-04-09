"""
Deploy a built slips presentation as a Databricks App.

Steps:
  1. Build the HTML with `node packages/cli/dist/cli.js build presentations/{name}/`
  2. Split into ≤4 MB binary chunks
  3. Upload app.py, app.yaml, and all chunks to the Databricks workspace
  4. Create or update the Databricks App
  5. Trigger a new deployment and wait until RUNNING
"""

from __future__ import annotations

import math
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .databricks_client import DatabricksClient


_APP_PY = '''\
import os, glob, http.server, socketserver

print("Loading chunks...", flush=True)
parts = []
for path in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chunk_*.bin"))):
    with open(path, "rb") as f:
        parts.append(f.read())
_content = b"".join(parts)
print(f"Loaded {len(_content)} bytes", flush=True)

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(_content)))
        self.end_headers()
        self.wfile.write(_content)
    def log_message(self, *a): pass

port = int(os.environ.get("DATABRICKS_APP_PORT", 8000))
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", port), Handler) as s:
    s.serve_forever()
'''

_APP_YAML = "command:\n  - python3\n  - app.py\n"

CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB


def build_presentation(name: str, slips_root: Optional[Path] = None) -> Path:
    """
    Run `node packages/cli/dist/cli.js build presentations/{name}/` inside
    the slips repo and return the path to the built HTML file.
    """
    if slips_root is None:
        slips_root = Path.home() / "slips"

    result = subprocess.run(
        [
            "node",
            str(slips_root / "packages" / "cli" / "dist" / "cli.js"),
            "build",
            f"presentations/{name}/",
        ],
        cwd=slips_root,
        capture_output=True,
        text=True,
        check=True,
    )

    built_html = slips_root / "presentations" / f"{name}.built.html"
    if not built_html.exists():
        raise FileNotFoundError(f"Build output not found: {built_html}")
    return built_html


def deploy(
    client: DatabricksClient,
    app_name: str,
    built_html: Path,
    ws_dir: Optional[str] = None,
    description: str = "Decision slides presentation",
    progress_callback=None,
) -> str:
    """
    Upload the built HTML to Databricks workspace and deploy as an App.
    Returns the app URL.

    Args:
        client: authenticated DatabricksClient
        app_name: Databricks App name (must be unique in the workspace)
        built_html: path to the *.built.html file
        ws_dir: workspace directory for app files (default: /Users/{email}/apps/{app_name})
        description: description shown in the Apps UI
        progress_callback: optional callable(message: str) for progress updates
    """
    def _log(msg: str):
        if progress_callback:
            progress_callback(msg)

    raw = built_html.read_bytes()
    n_chunks = math.ceil(len(raw) / CHUNK_SIZE)

    if ws_dir is None:
        me_resp = client._get("/api/2.0/preview/scim/v2/Me")
        email = me_resp.get("userName", "unknown")
        ws_dir = f"/Users/{email}/apps/{app_name}"

    _log(f"Creating workspace directory: {ws_dir}")
    client.mkdirs(ws_dir)

    _log("Uploading app.py …")
    client.upload_workspace_file(f"{ws_dir}/app.py", _APP_PY.encode())

    _log("Uploading app.yaml …")
    client.upload_workspace_file(f"{ws_dir}/app.yaml", _APP_YAML.encode())

    _log(f"Uploading {n_chunks} chunk(s) ({len(raw) / 1e6:.1f} MB total) …")
    for i in range(n_chunks):
        chunk = raw[i * CHUNK_SIZE : (i + 1) * CHUNK_SIZE]
        chunk_name = f"chunk_{i:03d}.bin"
        _log(f"  chunk {i + 1}/{n_chunks} …")
        client.upload_workspace_file(f"{ws_dir}/{chunk_name}", chunk)

    _log("Creating / verifying app …")
    client.create_or_get_app(app_name, description)

    _log("Deploying …")
    # Apps source_code_path must start with /Workspace/
    ws_source = ws_dir if ws_dir.startswith("/Workspace/") else f"/Workspace{ws_dir}"
    dep_id = client.deploy_app(app_name, ws_source)

    _log("Waiting for deployment to finish …")
    client.wait_for_deployment(app_name, dep_id)

    _log("Waiting for app to be RUNNING …")
    app_info = client.wait_for_app(app_name)
    return app_info.get("url", "")

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
import subprocess
from pathlib import Path
from typing import Optional

from .databricks_client import DatabricksClient
from .comments import inject as comments_inject


_APP_PY = '''\
"""
Databricks App — decision-slides presentation server with built-in comments.
Pure stdlib — no external dependencies required.

Routes:
  GET  /              → serves the deck HTML
  GET  /api/me        → returns the authenticated user's display name
  GET  /api/comments  → list comments (optional ?since=<id>)
  POST /api/comments  → post a new comment {"author": "...", "message": "..."}
"""
import os, json, sqlite3
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE_DIR = Path(__file__).parent

# ── Load deck HTML from chunks ──────────────────────────────────────────────
_parts = sorted(BASE_DIR.glob("chunk_*.bin"))
_html  = b"".join(p.read_bytes() for p in _parts)
print(f"Loaded {len(_html):,} bytes from {len(_parts)} chunks", flush=True)

# ── SQLite comment store ────────────────────────────────────────────────────
# Store outside the snapshot dir so comments survive redeployments.
# Override with COMMENTS_DB_PATH env var for a truly persistent location.
_default_db = Path(os.environ.get("COMMENTS_DB_PATH", "/tmp/decision-slides-comments.db"))
DB_PATH = _default_db

def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            author     TEXT NOT NULL,
            message    TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

# ── Identity helpers ────────────────────────────────────────────────────────
_ID_HEADERS = [
    "X-Forwarded-Email",
    "X-Databricks-User-Email",
    "X-Forwarded-User",
    "Remote-User",
]

def _user_name(handler) -> str:
    for h in _ID_HEADERS:
        v = handler.headers.get(h, "").strip()
        if not v or v.isdigit():  # skip empty or numeric-only IDs
            continue
        return v.split("@")[0].replace(".", " ").title() if "@" in v else v
    return ""

def _json(handler, data, status=200):
    body = json.dumps(data).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

# ── Request handler ──────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence access log

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(_html)))
            self.end_headers()
            self.wfile.write(_html)

        elif path == "/api/me":
            _json(self, {"name": _user_name(self)})

        elif path == "/api/comments":
            qs    = parse_qs(parsed.query)
            since = int(qs.get("since", ["0"])[0])
            conn  = _db()
            rows  = conn.execute(
                "SELECT id, author, message, created_at FROM comments WHERE id > ? ORDER BY id ASC",
                (since,)
            ).fetchall()
            conn.close()
            _json(self, [{"id": r[0], "author": r[1], "message": r[2], "created_at": r[3]} for r in rows])

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/api/comments":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            _json(self, {"error": "invalid JSON"}, 400)
            return

        author  = (_user_name(self) or str(body.get("author", ""))).strip() or "Anonymous"
        message = str(body.get("message", "")).strip()
        if not message:
            _json(self, {"error": "message is required"}, 400)
            return
        if len(message) > 2000:
            _json(self, {"error": "message too long (max 2000 chars)"}, 400)
            return

        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        conn = _db()
        cur  = conn.execute(
            "INSERT INTO comments (author, message, created_at) VALUES (?,?,?)",
            (author, message, created_at),
        )
        conn.commit()
        cid = cur.lastrowid
        conn.close()
        _json(self, {"id": cid, "author": author, "message": message, "created_at": created_at})

# ── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("DATABRICKS_APP_PORT", 8000))
    print(f"Starting on port {port}", flush=True)
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
'''

_APP_YAML = """\
command:
  - python3
  - app.py
"""

_REQUIREMENTS_TXT = """\
"""

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

    # Inject built-in comment panel
    _log("Injecting built-in comment panel …")
    html = raw.decode("utf-8", errors="replace")
    html = comments_inject(html)
    raw = html.encode("utf-8")

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

    _log("Uploading requirements.txt …")
    client.upload_workspace_file(f"{ws_dir}/requirements.txt", _REQUIREMENTS_TXT.encode())

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

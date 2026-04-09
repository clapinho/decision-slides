"""
Inject a floating Giscus comment panel into a built HTML presentation.

Giscus (https://giscus.app) stores comments as GitHub Discussions on a repo
you control. Anyone with the presentation link can read and post comments
without leaving the page. All they need is a GitHub account.

Setup (one-time):
  1. Enable GitHub Discussions on your repo
     (repo → Settings → Features → check Discussions)
  2. Install the Giscus GitHub App on that repo:
     https://github.com/apps/giscus
  3. Run: decision-slides giscus-setup <repo>
     to print the repo-id and category-id you'll need.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class GiscusConfig:
    repo: str = ""              # "owner/repo"
    repo_id: str = ""           # GitHub node ID (R_kg...)
    category: str = "General"  # Discussion category name
    category_id: str = ""       # Category node ID (DIC_...)
    term: str = ""              # Specific discussion term (defaults to presentation title)
    theme: str = "light"        # "light" | "dark" | "preferred_color_scheme"
    lang: str = "en"

    def is_set(self) -> bool:
        return bool(self.repo and self.repo_id and self.category_id)


def fetch_repo_id(repo: str, token: str = "") -> str:
    """Fetch the GitHub repo node_id via the REST API (no auth needed for public repos)."""
    owner, name = repo.split("/", 1)
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(f"https://api.github.com/repos/{owner}/{name}", headers=headers)
    resp.raise_for_status()
    return resp.json()["node_id"]


def fetch_categories(repo: str, token: str = "") -> list[dict]:
    """Fetch discussion categories via GitHub GraphQL. Returns [{id, name}, ...]."""
    owner, name = repo.split("/", 1)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        discussionCategories(first: 25) {
          nodes { id name }
        }
      }
    }
    """
    resp = requests.post(
        "https://api.github.com/graphql",
        headers=headers,
        json={"query": query, "variables": {"owner": owner, "name": name}},
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")
    return data["data"]["repository"]["discussionCategories"]["nodes"]


def fetch_category_id(repo: str, category_name: str, token: str = "") -> str:
    """Return the node ID for a named discussion category."""
    categories = fetch_categories(repo, token)
    for cat in categories:
        if cat["name"].lower() == category_name.lower():
            return cat["id"]
    if categories:
        names = [c["name"] for c in categories]
        raise ValueError(
            f"Category '{category_name}' not found in {repo}. "
            f"Available: {', '.join(names)}"
        )
    raise ValueError(f"No discussion categories found in {repo}. "
                     "Enable Discussions in the repo settings first.")


def inject(html: str, cfg: GiscusConfig) -> str:
    """
    Inject a floating comment button + slide-in panel into the built HTML.
    The panel loads Giscus inside an iframe on first open (lazy).
    """
    term = cfg.term or "decision-slides"
    widget = _build_widget(cfg, term)
    # Inject just before </body>
    if "</body>" in html:
        return html.replace("</body>", widget + "\n</body>", 1)
    return html + widget


def _build_widget(cfg: GiscusConfig, term: str) -> str:
    return f"""
<!-- Giscus comment panel injected by decision-slides -->
<style>
  #gc-btn {{
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    z-index: 9999;
    background: #7c3aed;
    color: #fff;
    border: none;
    border-radius: 50%;
    width: 3rem;
    height: 3rem;
    font-size: 1.25rem;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(0,0,0,0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.15s, box-shadow 0.15s;
  }}
  #gc-btn:hover {{ transform: scale(1.08); box-shadow: 0 6px 18px rgba(0,0,0,0.3); }}
  #gc-panel {{
    position: fixed;
    top: 0;
    right: -440px;
    width: 420px;
    max-width: 100vw;
    height: 100vh;
    background: #fff;
    z-index: 9998;
    box-shadow: -4px 0 24px rgba(0,0,0,0.12);
    transition: right 0.25s cubic-bezier(0.4,0,0.2,1);
    display: flex;
    flex-direction: column;
    font-family: system-ui, -apple-system, sans-serif;
  }}
  #gc-panel.gc-open {{ right: 0; }}
  #gc-header {{
    padding: 0.9rem 1.2rem;
    border-bottom: 1px solid #e5e7eb;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
  }}
  #gc-header span {{ font-size: 0.9rem; font-weight: 600; color: #111827; }}
  #gc-close {{
    background: none;
    border: none;
    font-size: 1.1rem;
    color: #9ca3af;
    cursor: pointer;
    padding: 0.2rem 0.4rem;
    border-radius: 4px;
    line-height: 1;
  }}
  #gc-close:hover {{ color: #374151; background: #f3f4f6; }}
  #gc-body {{
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
    -webkit-overflow-scrolling: touch;
  }}
  #gc-body .giscus {{ min-height: 200px; }}
</style>

<button id="gc-btn" title="Comments" aria-label="Open comments">&#x1F4AC;</button>
<div id="gc-panel" role="complementary" aria-label="Comments panel">
  <div id="gc-header">
    <span>&#x1F4AC; Comments</span>
    <button id="gc-close" aria-label="Close comments">&#x2715;</button>
  </div>
  <div id="gc-body" id="gc-body">
    <!-- Giscus loads here on first open -->
  </div>
</div>

<script>
(function () {{
  var btn   = document.getElementById('gc-btn');
  var panel = document.getElementById('gc-panel');
  var close = document.getElementById('gc-close');
  var body  = document.getElementById('gc-body');
  var loaded = false;

  function loadGiscus() {{
    if (loaded) return;
    loaded = true;
    var s = document.createElement('script');
    s.src = 'https://giscus.app/client.js';
    s.setAttribute('data-repo',             '{cfg.repo}');
    s.setAttribute('data-repo-id',          '{cfg.repo_id}');
    s.setAttribute('data-category',         '{cfg.category}');
    s.setAttribute('data-category-id',      '{cfg.category_id}');
    s.setAttribute('data-mapping',          'specific');
    s.setAttribute('data-term',             '{term}');
    s.setAttribute('data-strict',           '0');
    s.setAttribute('data-reactions-enabled','1');
    s.setAttribute('data-emit-metadata',    '0');
    s.setAttribute('data-input-position',   'bottom');
    s.setAttribute('data-theme',            '{cfg.theme}');
    s.setAttribute('data-lang',             '{cfg.lang}');
    s.setAttribute('crossorigin',           'anonymous');
    s.async = true;
    body.appendChild(s);
  }}

  btn.addEventListener('click', function () {{
    var isOpen = panel.classList.toggle('gc-open');
    if (isOpen) loadGiscus();
  }});
  close.addEventListener('click', function () {{
    panel.classList.remove('gc-open');
  }});
  document.addEventListener('keydown', function (e) {{
    if (e.key === 'Escape') panel.classList.remove('gc-open');
  }});
}})();
</script>
"""

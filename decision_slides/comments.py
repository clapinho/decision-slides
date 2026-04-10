"""
Built-in comment panel — no external accounts required.

Injects a floating 💬 panel into the built HTML that talks to the
FastAPI comment backend running inside the same Databricks App.

Comments are stored in SQLite on the app server. Anyone who can open
the deck can comment — their Databricks identity is used as the author
name automatically (no extra login needed).
"""

from __future__ import annotations

BRAND_PURPLE = "#7c3aed"


def inject(html: str) -> str:
    """Inject the built-in comment panel into the built HTML."""
    widget = _build_panel()
    idx = html.rfind("</body>")
    if idx != -1:
        return html[:idx] + widget + "\n</body>" + html[idx + len("</body>"):]
    return html + widget


def _build_panel() -> str:
    return f"""
<!-- Built-in comment panel — decision-slides -->
<style>
  #dc-btn {{
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    z-index: 9999;
    background: {BRAND_PURPLE};
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
  #dc-btn:hover {{ transform: scale(1.08); box-shadow: 0 6px 18px rgba(0,0,0,0.3); }}
  #dc-panel {{
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
    font-size: 0.9rem;
    color: #111827;
  }}
  #dc-panel.dc-open {{ right: 0; }}
  #dc-header {{
    padding: 0.9rem 1.2rem;
    border-bottom: 1px solid #e5e7eb;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
    background: #fafafa;
  }}
  #dc-header span {{ font-size: 0.9rem; font-weight: 600; }}
  #dc-close {{
    background: none; border: none; font-size: 1.1rem;
    color: #9ca3af; cursor: pointer; padding: 0.2rem 0.4rem;
    border-radius: 4px; line-height: 1;
  }}
  #dc-close:hover {{ color: #374151; background: #f3f4f6; }}
  #dc-list {{
    flex: 1; overflow-y: auto; padding: 0.75rem 1rem;
    display: flex; flex-direction: column; gap: 0.75rem;
  }}
  .dc-comment {{
    background: #f9fafb; border: 1px solid #e5e7eb;
    border-radius: 8px; padding: 0.65rem 0.85rem;
  }}
  .dc-comment-header {{
    display: flex; justify-content: space-between;
    align-items: baseline; margin-bottom: 0.3rem;
  }}
  .dc-author {{ font-weight: 600; font-size: 0.82rem; color: {BRAND_PURPLE}; }}
  .dc-time {{ font-size: 0.72rem; color: #9ca3af; }}
  .dc-msg {{ color: #374151; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }}
  #dc-empty {{ color: #9ca3af; font-size: 0.85rem; text-align: center; padding: 2rem 0; }}
  #dc-form {{
    flex-shrink: 0; padding: 0.75rem 1rem;
    border-top: 1px solid #e5e7eb; background: #fafafa;
    display: flex; flex-direction: column; gap: 0.5rem;
  }}
  #dc-name {{
    border: 1px solid #d1d5db; border-radius: 6px;
    padding: 0.45rem 0.65rem; font-size: 0.85rem; width: 100%;
    box-sizing: border-box; outline: none;
    font-family: inherit; color: #374151;
  }}
  #dc-name:focus {{ border-color: {BRAND_PURPLE}; box-shadow: 0 0 0 2px rgba(124,58,237,0.15); }}
  #dc-text {{
    border: 1px solid #d1d5db; border-radius: 6px;
    padding: 0.55rem 0.65rem; font-size: 0.85rem; width: 100%;
    box-sizing: border-box; resize: vertical; min-height: 70px;
    outline: none; font-family: inherit; color: #374151;
  }}
  #dc-text:focus {{ border-color: {BRAND_PURPLE}; box-shadow: 0 0 0 2px rgba(124,58,237,0.15); }}
  #dc-submit {{
    align-self: flex-end; background: {BRAND_PURPLE}; color: #fff;
    border: none; border-radius: 6px; padding: 0.45rem 1.1rem;
    font-size: 0.85rem; font-weight: 600; cursor: pointer;
    transition: background 0.15s;
  }}
  #dc-submit:hover {{ background: #6d28d9; }}
  #dc-submit:disabled {{ background: #c4b5fd; cursor: not-allowed; }}
  #dc-status {{ font-size: 0.78rem; color: #6b7280; min-height: 1em; }}
</style>

<button id="dc-btn" title="Comments" aria-label="Open comments">&#x1F4AC;</button>
<div id="dc-panel" role="complementary" aria-label="Comments panel">
  <div id="dc-header">
    <span>&#x1F4AC; Comments</span>
    <button id="dc-close" aria-label="Close">&#x2715;</button>
  </div>
  <div id="dc-list"><div id="dc-empty">No comments yet — be the first!</div></div>
  <div id="dc-form">
    <input id="dc-name" type="text" placeholder="Your name" maxlength="80" autocomplete="name" />
    <textarea id="dc-text" placeholder="Add a comment…" maxlength="2000"></textarea>
    <div style="display:flex;justify-content:space-between;align-items:center">
      <span id="dc-status"></span>
      <button id="dc-submit">Send</button>
    </div>
  </div>
</div>

<script>
(function () {{
  var btn    = document.getElementById('dc-btn');
  var panel  = document.getElementById('dc-panel');
  var close  = document.getElementById('dc-close');
  var list   = document.getElementById('dc-list');
  var empty  = document.getElementById('dc-empty');
  var name   = document.getElementById('dc-name');
  var text   = document.getElementById('dc-text');
  var submit = document.getElementById('dc-submit');
  var status = document.getElementById('dc-status');
  var lastId = 0;
  var pollTimer = null;

  /* ── Fetch current user name from the app backend ── */
  fetch('/api/me').then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.name) {{
      name.value = d.name;
      name.readOnly = true;
      name.style.color = '#6b7280';
    }}
  }}).catch(function() {{}});

  /* ── Render a comment element ── */
  function renderComment(c) {{
    var div = document.createElement('div');
    div.className = 'dc-comment';
    div.dataset.id = c.id;
    var d = new Date(c.created_at + 'Z');
    var ts = d.toLocaleDateString(undefined, {{month:'short',day:'numeric'}})
           + ' ' + d.toLocaleTimeString(undefined, {{hour:'2-digit',minute:'2-digit'}});
    div.innerHTML =
      '<div class="dc-comment-header">'
      + '<span class="dc-author">' + esc(c.author) + '</span>'
      + '<span class="dc-time">' + ts + '</span>'
      + '</div>'
      + '<div class="dc-msg">' + esc(c.message) + '</div>';
    return div;
  }}

  function esc(s) {{
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }}

  /* ── Load comments ── */
  function loadComments(since) {{
    var url = '/api/comments' + (since ? '?since=' + since : '');
    fetch(url).then(function(r) {{ return r.json(); }}).then(function(data) {{
      data.forEach(function(c) {{
        if (c.id <= lastId) return;
        empty.style.display = 'none';
        list.appendChild(renderComment(c));
        lastId = Math.max(lastId, c.id);
      }});
      if (data.length) list.scrollTop = list.scrollHeight;
    }}).catch(function() {{}});
  }}

  /* ── Open / close ── */
  btn.addEventListener('click', function () {{
    var open = panel.classList.toggle('dc-open');
    if (open) {{
      loadComments(0);
      pollTimer = setInterval(function() {{ loadComments(lastId); }}, 10000);
    }} else {{
      clearInterval(pollTimer);
    }}
  }});
  close.addEventListener('click', function () {{
    panel.classList.remove('dc-open');
    clearInterval(pollTimer);
  }});
  document.addEventListener('keydown', function (e) {{
    if (e.key === 'Escape') {{ panel.classList.remove('dc-open'); clearInterval(pollTimer); }}
  }});

  /* ── Submit ── */
  submit.addEventListener('click', function () {{
    var author  = name.value.trim() || 'Anonymous';
    var message = text.value.trim();
    if (!message) {{ status.textContent = 'Please write something.'; return; }}
    submit.disabled = true;
    status.textContent = 'Sending…';
    fetch('/api/comments', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{author: author, message: message}})
    }}).then(function(r) {{ return r.json(); }}).then(function(c) {{
      text.value = '';
      status.textContent = '';
      empty.style.display = 'none';
      list.appendChild(renderComment(c));
      list.scrollTop = list.scrollHeight;
      lastId = Math.max(lastId, c.id);
    }}).catch(function() {{
      status.textContent = 'Failed to send. Try again.';
    }}).finally(function() {{
      submit.disabled = false;
    }});
  }});

  /* submit on Ctrl+Enter / Cmd+Enter */
  text.addEventListener('keydown', function(e) {{
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submit.click();
  }});
}})();
</script>
"""

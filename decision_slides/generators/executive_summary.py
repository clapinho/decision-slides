"""Executive summary slide generator."""

from __future__ import annotations

from .base import BRAND_PURPLE


def generate(
    overview: str,
    results: list[str],
    to_discuss: list[str],
    tag: str = "",
    brand_color: str = BRAND_PURPLE,
) -> str:
    results_li = "\n".join(
        f'        <li><span class="es-arrow">→</span><span>{r}</span></li>'
        for r in results
    )
    discuss_li = "\n".join(
        f'        <li><span class="es-num">{i+1}.</span><span>{d}</span></li>'
        for i, d in enumerate(to_discuss)
    )

    return f"""<slip-slide id="executive-summary" transition="fade">
  <style>
    .es-root {{
      height: 100%;
      background: #ffffff;
      color: #111827;
      font-family: var(--slip-font);
      display: flex;
      flex-direction: column;
      padding: 2rem 3.5rem;
    }}
    .es-tag {{ font-size: 0.7rem; font-weight: 500; color: #9ca3af; letter-spacing: 0.04em; margin-bottom: 0.4rem; }}
    .es-title {{ font-size: 1.8rem; font-weight: 700; color: {brand_color}; margin: 0 0 0.9rem; line-height: 1.1; }}
    .es-intro {{ font-size: 0.82rem; color: #374151; line-height: 1.6; margin-bottom: 1.1rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 1rem; }}
    .es-section {{ margin-bottom: 0.9rem; }}
    .es-section-title {{ font-size: 0.68rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #374151; margin-bottom: 0.45rem; }}
    .es-section-title.discuss {{ text-transform: none; font-size: 0.75rem; letter-spacing: 0; }}
    .es-list {{ list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.3rem; }}
    .es-list li {{ display: flex; gap: 0.5rem; font-size: 0.78rem; color: #374151; line-height: 1.5; }}
    .es-arrow {{ color: {brand_color}; flex-shrink: 0; font-size: 0.85rem; margin-top: 0.05rem; }}
    .es-numbered {{ list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.3rem; }}
    .es-numbered li {{ display: flex; gap: 0.5rem; font-size: 0.78rem; color: #374151; line-height: 1.5; }}
    .es-num {{ color: {brand_color}; flex-shrink: 0; font-weight: 600; font-size: 0.78rem; }}
  </style>
  <div class="es-root">
    {f'<div class="es-tag">{tag}</div>' if tag else ""}
    <h2 class="es-title">Executive Summary</h2>
    <p class="es-intro">{overview}</p>
    <div class="es-section">
      <div class="es-section-title">Results</div>
      <ul class="es-list">
{results_li}
      </ul>
    </div>
    <div class="es-section">
      <div class="es-section-title discuss">To be discussed</div>
      <ol class="es-numbered">
{discuss_li}
      </ol>
    </div>
  </div>
  <slip-notes>Walk through Results first, then open the floor on "To be discussed" items.</slip-notes>
</slip-slide>
"""

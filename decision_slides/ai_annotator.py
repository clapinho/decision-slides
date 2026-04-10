"""
AI-powered slide annotator using LiteLLM.

Analyzes chart images and generates concise descriptions for slide text.
Works with any LLM provider supported by LiteLLM (Anthropic, OpenAI, Azure, etc.)

Configuration (via env vars):
    ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN  — Anthropic / proxy key
    ANTHROPIC_BASE_URL                          — Custom proxy base URL (optional)
    LITELLM_MODEL                               — Override default model (optional)

Usage:
    from decision_slides.ai_annotator import SlideAnnotator

    annotator = SlideAnnotator()
    description = annotator.describe_chart(img_bytes, context={"metric": "loss_rate"})
"""

from __future__ import annotations

import base64
import os
from typing import Any


DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a concise financial analyst writing 2-sentence slide annotations for a credit risk presentation.
No markdown, no bullet points. Plain text only."""

COHORT_USER_PROMPT = """\
This is a cohort monitoring chart segmented by Aki risk bands: low Aki (21, 25), high Aki (26, 27), marginal (28). \
There are two prediction lines: actuals predictions (coloured solid lines per band) and pClip predictions (grey dotted). \
Black dashed = actuals. Short term = months 1–5, long term = months > 5.

In 2–3 short sentences, for each Aki group state:
- Whether actuals are above or below actuals predictions (short term and long term)
- Whether actuals are above or below pClip predictions (short term and long term)

Be concise. Example format: "Low Aki: actuals [above/below/matching] actuals predictions and [above/below/matching] \
pClip short term; [above/below/matching] actuals predictions and [above/below/matching] pClip long term. High Aki: … Marginal Aki 28: …"

Metric: {metric}
{extra_context}"""

GENERIC_USER_PROMPT = """This is a slide chart titled "{title}".
Write a 2–3 sentence annotation summarizing the key insight a decision-maker should take from this chart.
No markdown, plain text only."""


class SlideAnnotator:
    """Generates chart descriptions using vision LLMs via LiteLLM."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        max_tokens: int = 180,
    ):
        self.model = model or os.environ.get("LITELLM_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens
        # Support Nubank's ANTHROPIC_AUTH_TOKEN convention
        self._api_key = (
            api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        )

    def _completion(self, messages: list[dict]) -> str:
        import litellm  # lazy import so the module loads without litellm installed

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key

        resp = litellm.completion(**kwargs)
        return resp.choices[0].message.content.strip()

    def describe_chart(
        self,
        img_bytes: bytes,
        title: str = "",
        metric: str = "",
        extra_context: str = "",
    ) -> str:
        """
        Analyze a chart image and return a short slide description.

        Args:
            img_bytes: Raw PNG/JPEG bytes of the chart
            title:     Slide title (used in the prompt for context)
            metric:    Metric name for cohort monitoring charts
            extra_context: Any additional context to include in the prompt

        Returns:
            Plain-text description (2–3 sentences, ~50 words)
        """
        b64 = base64.b64encode(img_bytes).decode()

        if metric:
            user_text = COHORT_USER_PROMPT.format(
                metric=metric.replace("_", " "),
                extra_context=extra_context,
            )
        else:
            user_text = GENERIC_USER_PROMPT.format(title=title or "chart")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                    {"type": "text", "text": user_text},
                ],
            },
        ]
        return self._completion(messages)

    def describe_chart_from_b64(
        self,
        b64: str,
        title: str = "",
        metric: str = "",
        extra_context: str = "",
    ) -> str:
        """Convenience wrapper that takes a base64 string instead of bytes."""
        return self.describe_chart(
            base64.b64decode(b64),
            title=title,
            metric=metric,
            extra_context=extra_context,
        )


def make_annotator(**kwargs) -> SlideAnnotator:
    """Factory — returns a SlideAnnotator configured from the environment."""
    return SlideAnnotator(**kwargs)

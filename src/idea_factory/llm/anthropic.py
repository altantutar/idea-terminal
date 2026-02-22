"""Anthropic Claude LLM provider."""

from __future__ import annotations

import anthropic

from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    """Uses the Anthropic SDK to call Claude models."""

    def __init__(self, api_key: str, model: str, max_retries: int = 2) -> None:
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_retries = max_retries

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # Track usage for cost monitoring
        self._last_usage = {
            "input_tokens": getattr(response.usage, "input_tokens", 0),
            "output_tokens": getattr(response.usage, "output_tokens", 0),
        }
        return response.content[0].text  # type: ignore[union-attr]

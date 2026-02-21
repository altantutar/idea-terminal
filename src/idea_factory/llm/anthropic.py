"""Anthropic Claude LLM provider."""

from __future__ import annotations

import anthropic

from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    """Uses the Anthropic SDK to call Claude models."""

    def __init__(self, api_key: str, model: str) -> None:
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text

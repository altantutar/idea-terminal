"""OpenAI LLM provider."""

from __future__ import annotations

import openai

from .base import LLMProvider


class OpenAIProvider(LLMProvider):
    """Uses the OpenAI SDK to call GPT models with JSON mode."""

    def __init__(self, api_key: str, model: str, max_retries: int = 2) -> None:
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.max_retries = max_retries

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=4096,
        )
        # Track usage for cost monitoring
        usage = response.usage
        self._last_usage = {
            "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
        }
        return response.choices[0].message.content or ""

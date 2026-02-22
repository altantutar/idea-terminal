"""Abstract LLM provider interface."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError
from rich.console import Console

T = TypeVar("T", bound=BaseModel)

console = Console(stderr=True)

# Fallback used when no max_retries is injected via constructor.
_DEFAULT_MAX_RETRIES = 2


class LLMProvider(ABC):
    """Base class every LLM provider must implement."""

    max_retries: int = _DEFAULT_MAX_RETRIES
    _last_usage: dict = {}  # populated by subclasses after each call

    def get_last_usage(self) -> dict:
        """Return token usage from the most recent generate_text call."""
        return getattr(self, "_last_usage", {})

    @abstractmethod
    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts and return raw text response."""
        ...

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
    ) -> T:
        """Generate structured output, retrying on parse failures."""
        import logging

        logger = logging.getLogger("idea_factory.llm")
        max_retries = self.max_retries
        last_error: Exception | None = None
        for attempt in range(1 + max_retries):
            raw = self.generate_text(system_prompt, user_prompt)
            try:
                # Try to extract JSON from the response
                text = raw.strip()
                # Handle markdown-wrapped JSON
                if text.startswith("```"):
                    lines = text.split("\n")
                    # Remove first and last ``` lines
                    lines = [ln for ln in lines if not ln.strip().startswith("```")]
                    text = "\n".join(lines)
                return response_model.model_validate_json(text)
            except (ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning(
                    "JSON parse attempt %d/%d failed: %s",
                    attempt + 1,
                    1 + max_retries,
                    exc,
                )
                if attempt < max_retries:
                    console.print(f"  [dim]Parse attempt {attempt + 1} failed, retrying...[/dim]")
                    # Append correction hint to the user prompt
                    user_prompt = (
                        user_prompt + f"\n\n[SYSTEM: Your previous response was not valid JSON "
                        f"matching the schema. Error: {exc}. "
                        f"Please respond with ONLY valid JSON, no markdown.]"
                    )
        raise ValueError(
            f"Failed to parse LLM output after {1 + max_retries} attempts: {last_error}"
        )

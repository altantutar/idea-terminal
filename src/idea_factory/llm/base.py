"""Abstract LLM provider interface."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError
from rich.console import Console

T = TypeVar("T", bound=BaseModel)

console = Console(stderr=True)

MAX_RETRIES = 2


class LLMProvider(ABC):
    """Base class every LLM provider must implement."""

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
        last_error: Exception | None = None
        for attempt in range(1 + MAX_RETRIES):
            raw = self.generate_text(system_prompt, user_prompt)
            try:
                # Try to extract JSON from the response
                text = raw.strip()
                # Handle markdown-wrapped JSON
                if text.startswith("```"):
                    lines = text.split("\n")
                    # Remove first and last ``` lines
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    text = "\n".join(lines)
                return response_model.model_validate_json(text)
            except (ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    console.print(
                        f"  [dim]Parse attempt {attempt + 1} failed, retrying...[/dim]"
                    )
                    # Append correction hint to the user prompt
                    user_prompt = (
                        user_prompt
                        + f"\n\n[SYSTEM: Your previous response was not valid JSON "
                        f"matching the schema. Error: {exc}. "
                        f"Please respond with ONLY valid JSON, no markdown.]"
                    )
        raise ValueError(
            f"Failed to parse LLM output after {1 + MAX_RETRIES} attempts: {last_error}"
        )

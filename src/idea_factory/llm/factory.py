"""Provider factory — picks the right LLM backend based on config."""

from __future__ import annotations

from idea_factory.config import Settings

from .anthropic import AnthropicProvider
from .base import LLMProvider
from .openai import OpenAIProvider


def get_provider(settings: Settings) -> LLMProvider:
    """Instantiate the configured LLM provider."""
    if settings.llm_provider == "anthropic":
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
            model=settings.model,
        )
    if settings.llm_provider == "openai":
        return OpenAIProvider(
            api_key=settings.openai_api_key,  # type: ignore[arg-type]
            model=settings.model,
        )
    raise ValueError(f"Unknown provider: {settings.llm_provider}")

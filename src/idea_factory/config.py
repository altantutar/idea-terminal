"""Settings and configuration, read from environment variables."""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o",
}


class Settings:
    """Application settings sourced from env vars with sensible defaults."""

    def __init__(self) -> None:
        self.llm_provider: str = os.getenv(
            "IDEA_FACTORY_LLM_PROVIDER", "anthropic"
        ).lower()
        if self.llm_provider not in ("anthropic", "openai"):
            raise ValueError(
                f"Unsupported LLM provider: {self.llm_provider}. "
                "Use 'anthropic' or 'openai'."
            )

        self.anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key: str | None = os.getenv("OPENAI_API_KEY")

        self.model: str = os.getenv(
            "IDEA_FACTORY_MODEL", DEFAULT_MODELS[self.llm_provider]
        )

        self.db_path: Path = Path(
            os.getenv("IDEA_FACTORY_DB_PATH", str(Path.home() / ".idea-factory" / "ideas.db"))
        )

        self.verbose: bool = os.getenv("IDEA_FACTORY_VERBOSE", "").lower() in (
            "1",
            "true",
            "yes",
        )

    def active_api_key(self) -> str | None:
        """Return the API key for the currently selected provider."""
        if self.llm_provider == "anthropic":
            return self.anthropic_api_key
        return self.openai_api_key

    def set_provider(self, provider: str, api_key: str | None = None) -> None:
        """Override the provider (and optionally the key) after construction."""
        provider = provider.lower()
        if provider not in ("anthropic", "openai"):
            raise ValueError(f"Unsupported provider: {provider}")
        self.llm_provider = provider
        self.model = os.getenv("IDEA_FACTORY_MODEL", DEFAULT_MODELS[provider])
        if api_key:
            if provider == "anthropic":
                self.anthropic_api_key = api_key
            else:
                self.openai_api_key = api_key

    def validate(self) -> None:
        """Raise if the required API key for the chosen provider is missing."""
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when using the Anthropic provider.")
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when using the OpenAI provider.")

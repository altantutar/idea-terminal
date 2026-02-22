"""Settings and configuration, read from environment variables.

Loads a ``.env`` file (if present) via *python-dotenv* before reading env vars
so users can manage keys and tuning knobs without exporting in every shell.
"""

from __future__ import annotations

import os
from pathlib import Path

# Load .env file before anything reads os.getenv
try:
    from dotenv import load_dotenv

    load_dotenv()  # searches CWD and parents for .env
except ModuleNotFoundError:  # python-dotenv is optional
    pass


DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o",
}

DOMAIN_CHOICES = [
    "Software engineering",
    "Back-office automation",
    "Marketing and copywriting",
    "Sales and CRM",
    "Finance and accounting",
    "Data analysis and BI",
    "Academic research",
    "Cybersecurity",
    "Customer service",
    "Gaming and interactive media",
    "Document and presentation creation",
    "Education and tutoring",
    "E-commerce operations",
    "Medicine and healthcare",
    "Legal",
    "Travel and logistics",
]


def _env_int(key: str, default: int) -> int:
    """Read an env var as int, falling back to *default*."""
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    """Read an env var as float, falling back to *default*."""
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class Settings:
    """Application settings sourced from env vars with sensible defaults."""

    def __init__(self) -> None:
        self.llm_provider: str = os.getenv("IDEA_FACTORY_LLM_PROVIDER", "anthropic").lower()
        if self.llm_provider not in ("anthropic", "openai"):
            raise ValueError(
                f"Unsupported LLM provider: {self.llm_provider}. Use 'anthropic' or 'openai'."
            )

        self.anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key: str | None = os.getenv("OPENAI_API_KEY")

        self.model: str = os.getenv("IDEA_FACTORY_MODEL", DEFAULT_MODELS[self.llm_provider])

        self.db_path: Path = Path(
            os.getenv("IDEA_FACTORY_DB_PATH", str(Path.home() / ".idea-factory" / "ideas.db"))
        )

        self.verbose: bool = os.getenv("IDEA_FACTORY_VERBOSE", "").lower() in (
            "1",
            "true",
            "yes",
        )

        # --- Pipeline tuning knobs (previously hardcoded) ---
        self.top_k: int = _env_int("IDEA_FACTORY_TOP_K", 2)
        self.max_winners: int = _env_int("IDEA_FACTORY_MAX_WINNERS", 10)
        self.max_retries: int = _env_int("IDEA_FACTORY_MAX_RETRIES", 2)
        self.reflexion_max_rounds: int = _env_int("IDEA_FACTORY_REFLEXION_MAX_ROUNDS", 2)
        self.trending_cache_ttl: int = _env_int("IDEA_FACTORY_TRENDING_CACHE_TTL", 600)
        self.pace_between_ideas: float = _env_float("IDEA_FACTORY_PACE_BETWEEN_IDEAS", 2.0)
        self.pace_between_loops: float = _env_float("IDEA_FACTORY_PACE_BETWEEN_LOOPS", 5.0)

        # --- Logging ---
        self.log_file: str | None = os.getenv("IDEA_FACTORY_LOG_FILE")
        self.log_level: str = os.getenv("IDEA_FACTORY_LOG_LEVEL", "INFO").upper()

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

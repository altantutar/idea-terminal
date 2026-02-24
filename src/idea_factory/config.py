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
    "gemini": "gemini-3.1-pro-preview",
}

DEFAULT_QUICK_DOMAINS = [
    "Software engineering",
    "Finance and accounting",
    "Data analysis and BI",
]

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


DOMAIN_NICHES: dict[str, list[str]] = {
    "Software engineering": [
        "Developer tooling & DX",
        "CI/CD and deployment",
        "Code review & quality",
        "API management",
        "Legacy modernization",
    ],
    "Back-office automation": [
        "Invoice processing",
        "Procurement workflows",
        "HR onboarding",
        "Compliance reporting",
        "Expense management",
    ],
    "Marketing and copywriting": [
        "SEO content pipelines",
        "Ad creative testing",
        "Brand voice consistency",
        "Influencer campaign ops",
        "Personalization engines",
    ],
    "Sales and CRM": [
        "Pipeline forecasting",
        "Lead enrichment",
        "Sales coaching",
        "Contract lifecycle",
        "Revenue operations",
    ],
    "Finance and accounting": [
        "Cash flow forecasting",
        "Tax automation",
        "Audit trail management",
        "Treasury operations",
        "Financial close automation",
    ],
    "Data analysis and BI": [
        "Self-serve analytics",
        "Data quality monitoring",
        "Metric layer management",
        "Anomaly detection",
        "Data catalog & lineage",
    ],
    "Academic research": [
        "Literature review automation",
        "Grant writing assistance",
        "Reproducibility tooling",
        "Lab data management",
        "Peer review workflows",
    ],
    "Cybersecurity": [
        "Threat intelligence",
        "Security posture management",
        "Incident response automation",
        "Supply chain security",
        "Identity & access governance",
    ],
    "Customer service": [
        "Ticket routing & triage",
        "Knowledge base curation",
        "Agent quality assurance",
        "Proactive outreach",
        "Voice-of-customer analytics",
    ],
    "Gaming and interactive media": [
        "Procedural content generation",
        "Player behavior analytics",
        "In-game economy balancing",
        "Community moderation",
        "Accessibility tooling",
    ],
    "Document and presentation creation": [
        "Template intelligence",
        "Version control for docs",
        "Regulatory document assembly",
        "Visual design automation",
        "Translation & localization",
    ],
    "Education and tutoring": [
        "Adaptive learning paths",
        "Assessment generation",
        "Student engagement analytics",
        "Credential verification",
        "Cohort-based learning ops",
    ],
    "E-commerce operations": [
        "Inventory forecasting",
        "Dynamic pricing",
        "Returns & refund automation",
        "Product catalog enrichment",
        "Marketplace multi-channel sync",
    ],
    "Medicine and healthcare": [
        "Clinical trials management",
        "Remote patient monitoring",
        "Medical billing automation",
        "Clinical decision support",
        "Provider credentialing",
    ],
    "Legal": [
        "Contract analysis",
        "E-discovery automation",
        "Regulatory change tracking",
        "IP portfolio management",
        "Legal billing & matter mgmt",
    ],
    "Travel and logistics": [
        "Route optimization",
        "Freight matching",
        "Customs & compliance",
        "Last-mile delivery",
        "Travel expense reconciliation",
    ],
}


def build_domain_niches_hint(domains: list[str]) -> str:
    """Build a hint string with sub-niches for selected domains."""
    lines: list[str] = []
    for domain in domains:
        niches = DOMAIN_NICHES.get(domain, [])
        if niches:
            lines.append(f"  {domain}: {', '.join(niches)}")
    if not lines:
        return ""
    hint = "== DOMAIN SUB-NICHES (explore these specific verticals) ==\n" + "\n".join(lines)
    if len(domains) > 1:
        hint += (
            "\n\nConsider ideas at the INTERSECTION of these domains — "
            "cross-domain ideas are often the most novel."
        )
    return hint


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
        if self.llm_provider not in ("anthropic", "openai", "gemini"):
            raise ValueError(
                "Unsupported LLM provider: "
                f"{self.llm_provider}. Use 'anthropic', 'openai', or 'gemini'."
            )

        self.anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
        self.gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY")

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
        if self.llm_provider == "openai":
            return self.openai_api_key
        return self.gemini_api_key

    def set_provider(self, provider: str, api_key: str | None = None) -> None:
        """Override the provider (and optionally the key) after construction."""
        provider = provider.lower()
        if provider not in ("anthropic", "openai", "gemini"):
            raise ValueError(f"Unsupported provider: {provider}")
        self.llm_provider = provider
        self.model = os.getenv("IDEA_FACTORY_MODEL", DEFAULT_MODELS[provider])
        if api_key:
            if provider == "anthropic":
                self.anthropic_api_key = api_key
            elif provider == "openai":
                self.openai_api_key = api_key
            else:
                self.gemini_api_key = api_key

    def validate(self) -> None:
        """Raise if the required API key for the chosen provider is missing."""
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when using the Anthropic provider.")
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when using the OpenAI provider.")
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when using the Gemini provider.")

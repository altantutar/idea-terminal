"""Trending topics fetcher — injects real-world context into the Creator."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from rich.console import Console

console = Console()


@dataclass
class TrendingContext:
    """Cached trending topic data."""

    topics: list[str] = field(default_factory=list)
    fetched_at: float = 0.0


# Module-level cache
_cache = TrendingContext()
_CACHE_TTL = 600  # 10 minutes


def _search(query: str, max_results: int = 5) -> list[str]:
    """Run a DuckDuckGo search and return result titles."""
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [r.get("title", "") for r in results if r.get("title")]
    except Exception:
        return []


def fetch_trending() -> TrendingContext:
    """Fetch trending tech/startup topics. Cached for 10 minutes."""
    global _cache

    now = time.time()
    if _cache.topics and (now - _cache.fetched_at) < _CACHE_TTL:
        return _cache

    topics: list[str] = []

    # Startup launches & community
    launch_queries = [
        "Product Hunt trending today",
        "YC latest batch companies",
        "BetaList new startups this week",
        "AngelList trending startups",
        "Indie Hackers top posts this week",
    ]
    # Industry analysis & thought leadership
    analysis_queries = [
        "TechCrunch startup launches this week",
        "a16z blog latest market trends",
        "CB Insights industry reports 2026",
        "First Round Review startup advice",
        "Crunchbase trending funding rounds",
    ]
    # Broader signals
    signal_queries = [
        "Hacker News top stories today",
        "AI startup trends this week",
        "trending startup ideas 2026",
    ]

    for query in launch_queries + analysis_queries + signal_queries:
        results = _search(query, max_results=3)
        topics.extend(results)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for t in topics:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique.append(t)

    _cache = TrendingContext(topics=unique[:25], fetched_at=now)
    return _cache


def build_trending_prefix(ctx: TrendingContext) -> str:
    """Format trending topics as a Creator prompt injection."""
    if not ctx.topics:
        return ""

    lines = ["[TRENDING CONTEXT — use these as inspiration, not constraints]"]
    for topic in ctx.topics[:15]:
        lines.append(f"- {topic}")
    lines.append(
        "Draw inspiration from these real-world signals. "
        "Build on emerging trends, solve problems hinted at above, "
        "or find contrarian angles the market is missing."
    )
    return "\n".join(lines)


def fetch_persona_context(handle: str) -> str:
    """Search for a @handle's public opinions to enrich persona description."""
    queries = [
        f"{handle} startup opinions",
        f"{handle} investment thesis technology",
    ]
    snippets: list[str] = []
    for q in queries:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(q, max_results=3))
                for r in results:
                    body = r.get("body", "")
                    if body:
                        snippets.append(body[:200])
        except Exception:
            pass

    if not snippets:
        return ""

    return " | ".join(snippets[:4])

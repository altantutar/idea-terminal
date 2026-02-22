"""Trending topics fetcher — injects real-world context into the Creator."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from rich.console import Console
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger("idea_factory.trending")
console = Console()


@dataclass
class InspirationSource:
    """A single inspiration source from trending topic searches."""

    title: str
    url: str
    platform: str  # e.g. "Product Hunt", "Hacker News", "Reddit"
    snippet: str = ""


@dataclass
class TrendingContext:
    """Cached trending topic data with full source information."""

    sources: list[InspirationSource] = field(default_factory=list)
    fetched_at: float = 0.0

    @property
    def topics(self) -> list[str]:
        """Backwards-compatible property returning just titles."""
        return [s.title for s in self.sources]


# Module-level cache
_cache = TrendingContext()
# Default TTL; overridden by Settings.trending_cache_ttl when passed to fetch_trending()
_DEFAULT_CACHE_TTL = 600  # 10 minutes


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _search_with_retry(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo search with exponential backoff. Returns full result dicts."""
    from duckduckgo_search import DDGS

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", "")[:200] if r.get("body") else "",
            }
            for r in results
            if r.get("title")
        ]


def _search(query: str, max_results: int = 5) -> list[dict]:
    """Run a DuckDuckGo search with retry. Returns empty list on failure."""
    try:
        return _search_with_retry(query, max_results)
    except Exception as exc:
        logger.warning("DuckDuckGo search failed for %r after retries: %s", query, exc)
        return []


def _detect_platform(query: str) -> str:
    """Detect the platform from the search query."""
    query_lower = query.lower()
    if "product hunt" in query_lower:
        return "Product Hunt"
    elif "hacker news" in query_lower:
        return "Hacker News"
    elif "reddit" in query_lower:
        return "Reddit"
    elif "techcrunch" in query_lower:
        return "TechCrunch"
    elif "indie hackers" in query_lower:
        return "Indie Hackers"
    elif "betalist" in query_lower:
        return "BetaList"
    elif "yc" in query_lower or "y combinator" in query_lower:
        return "Y Combinator"
    elif "angellist" in query_lower:
        return "AngelList"
    elif "a16z" in query_lower:
        return "a16z"
    elif "crunchbase" in query_lower:
        return "Crunchbase"
    elif "cb insights" in query_lower:
        return "CB Insights"
    else:
        return "Web"


def fetch_trending(cache_ttl: int | None = None) -> TrendingContext:
    """Fetch trending tech/startup topics. Cached for *cache_ttl* seconds."""
    global _cache

    ttl = cache_ttl if cache_ttl is not None else _DEFAULT_CACHE_TTL
    now = time.time()
    if _cache.sources and (now - _cache.fetched_at) < ttl:
        return _cache

    sources: list[InspirationSource] = []

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
        platform = _detect_platform(query)
        for r in results:
            sources.append(
                InspirationSource(
                    title=r["title"],
                    url=r["url"],
                    platform=platform,
                    snippet=r.get("snippet", ""),
                )
            )

    # Deduplicate by title (case-insensitive) while preserving order
    seen: set[str] = set()
    unique: list[InspirationSource] = []
    for src in sources:
        key = src.title.lower()
        if key not in seen:
            seen.add(key)
            unique.append(src)

    _cache = TrendingContext(sources=unique[:25], fetched_at=now)
    return _cache


def build_trending_prefix(ctx: TrendingContext) -> str:
    """Format trending topics as a Creator prompt injection with source attribution."""
    if not ctx.sources:
        return ""

    lines = ["[TRENDING CONTEXT — use these as inspiration, not constraints]"]
    for src in ctx.sources[:15]:
        # Include platform and URL for attribution
        lines.append(f"- [{src.platform}] {src.title}")
        if src.url:
            lines.append(f"  Source: {src.url}")
    lines.append("")
    lines.append(
        "Draw inspiration from these real-world signals. "
        "Build on emerging trends, solve problems hinted at above, "
        "or find contrarian angles the market is missing."
    )
    lines.append("")
    lines.append(
        "IMPORTANT: For each idea you generate, include an 'inspired_by' field "
        "listing the source(s) that inspired it. Format: "
        '[{"title": "...", "url": "...", "platform": "..."}]'
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

            @retry(
                stop=stop_after_attempt(2),
                wait=wait_exponential(multiplier=1, min=1, max=4),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            )
            def _persona_search(query: str) -> list[dict]:
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=3))

            results = _persona_search(q)
            for r in results:
                body = r.get("body", "")
                if body:
                    snippets.append(body[:200])
        except Exception as exc:
            logger.warning("Persona context search failed for %r after retries: %s", q, exc)

    if not snippets:
        return ""

    return " | ".join(snippets[:4])

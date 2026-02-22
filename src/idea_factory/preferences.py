"""Preference learning — tracks and applies user taste over time."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from idea_factory.db import repository as repo


@dataclass
class PreferenceState:
    """In-memory representation of learned user preferences."""

    domain_weights: dict[str, float] = field(default_factory=dict)
    reject_tag_weights: dict[str, float] = field(default_factory=dict)
    channel_weights: dict[str, float] = field(default_factory=dict)
    hard_nos: list[str] = field(default_factory=list)
    archetype_weights: dict[str, float] = field(default_factory=dict)


def load_preferences(conn: sqlite3.Connection) -> PreferenceState:
    """Load preference state from the DB."""
    raw = repo.load_preferences(conn)
    return PreferenceState(
        domain_weights=raw.get("domain_weights", {}),
        reject_tag_weights=raw.get("reject_tag_weights", {}),
        channel_weights=raw.get("channel_weights", {}),
        hard_nos=raw.get("hard_nos", []),
        archetype_weights=raw.get("archetype_weights", {}),
    )


def save_preferences(conn: sqlite3.Connection, prefs: PreferenceState) -> None:
    """Persist preference state to the DB."""
    repo.save_preference(conn, "domain_weights", prefs.domain_weights)
    repo.save_preference(conn, "reject_tag_weights", prefs.reject_tag_weights)
    repo.save_preference(conn, "channel_weights", prefs.channel_weights)
    repo.save_preference(conn, "hard_nos", prefs.hard_nos)
    repo.save_preference(conn, "archetype_weights", prefs.archetype_weights)


# Weight deltas per feedback decision
_DECISION_MULTIPLIER = {
    "love": 2.0,
    "like": 1.0,
    "meh": -0.5,
    "hate": -2.0,
}


def update_preferences(
    prefs: PreferenceState,
    feedback: dict,
    idea: dict,
    judge_output: dict | None = None,
) -> PreferenceState:
    """Apply weight updates based on user feedback."""
    decision = feedback["decision"]
    mult = _DECISION_MULTIPLIER.get(decision, 0.0)

    # Domain weight
    domain = idea.get("domain", "")
    if domain:
        prefs.domain_weights[domain] = prefs.domain_weights.get(domain, 0.0) + mult

    # Tag weights (positive for loved tags, negative for hated)
    for tag in idea.get("tags", []):
        if isinstance(tag, str):
            if decision in ("hate", "meh"):
                prefs.reject_tag_weights[tag] = prefs.reject_tag_weights.get(tag, 0.0) + abs(mult)
            else:
                # Reduce reject weight if the user likes ideas with this tag
                prefs.reject_tag_weights[tag] = max(
                    0.0, prefs.reject_tag_weights.get(tag, 0.0) - abs(mult)
                )

    # Archetype weight from judge
    if judge_output:
        archetype = judge_output.get("archetype", "")
        if archetype:
            prefs.archetype_weights[archetype] = prefs.archetype_weights.get(archetype, 0.0) + mult

    # Hard no on hate
    if decision == "hate":
        name = idea.get("name", "")
        if name and name not in prefs.hard_nos:
            prefs.hard_nos.append(name)

    return prefs


def build_taste_prefix(prefs: PreferenceState) -> str:
    """Generate a natural-language taste hint to inject into the Creator prompt."""
    lines: list[str] = []

    # Preferred domains
    liked = sorted(
        ((d, w) for d, w in prefs.domain_weights.items() if w > 0),
        key=lambda x: -x[1],
    )
    if liked:
        lines.append("Preferred domains: " + ", ".join(d for d, _ in liked[:5]))

    # Avoided domains
    disliked = sorted(
        ((d, w) for d, w in prefs.domain_weights.items() if w < -1),
        key=lambda x: x[1],
    )
    if disliked:
        lines.append("Avoid domains: " + ", ".join(d for d, _ in disliked[:5]))

    # Tags to avoid
    bad_tags = sorted(
        ((t, w) for t, w in prefs.reject_tag_weights.items() if w > 2),
        key=lambda x: -x[1],
    )
    if bad_tags:
        lines.append("Avoid tags/themes: " + ", ".join(t for t, _ in bad_tags[:8]))

    # Preferred archetypes
    liked_arch = sorted(
        ((a, w) for a, w in prefs.archetype_weights.items() if w > 0),
        key=lambda x: -x[1],
    )
    if liked_arch:
        lines.append("Preferred idea archetypes: " + ", ".join(a for a, _ in liked_arch[:5]))

    if not lines:
        return ""
    return "\n\nUser taste profile:\n" + "\n".join(f"- {line}" for line in lines) + "\n"

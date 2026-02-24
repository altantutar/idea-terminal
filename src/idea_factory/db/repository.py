"""CRUD operations for ideas, agent outputs, feedback, and preferences."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

# ---------------------------------------------------------------------------
# Ideas
# ---------------------------------------------------------------------------


def save_idea(conn: sqlite3.Connection, idea: dict, source: str = "ai") -> int:
    """Insert an idea row and return its id."""
    cur = conn.execute(
        """INSERT INTO ideas (name, one_liner, domain, problem, solution,
                              target_user, monetization, region, tags, inspired_by,
                              why_now, moat, unfair_insight, source)
           VALUES (:name, :one_liner, :domain, :problem, :solution,
                   :target_user, :monetization, :region, :tags, :inspired_by,
                   :why_now, :moat, :unfair_insight, :source)""",
        {
            **idea,
            "tags": json.dumps(idea.get("tags", [])),
            "inspired_by": json.dumps(idea.get("inspired_by", [])),
            "why_now": idea.get("why_now", ""),
            "moat": idea.get("moat", ""),
            "unfair_insight": idea.get("unfair_insight", ""),
            "source": source,
        },
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def update_idea_status(
    conn: sqlite3.Connection,
    idea_id: int,
    status: str,
    composite_score: float | None = None,
) -> None:
    if composite_score is not None:
        conn.execute(
            "UPDATE ideas SET status = ?, composite_score = ? WHERE id = ?",
            (status, composite_score, idea_id),
        )
    else:
        conn.execute("UPDATE ideas SET status = ? WHERE id = ?", (status, idea_id))
    conn.commit()


def list_ideas(conn: sqlite3.Connection, status: str | None = None) -> list[dict]:
    if status:
        rows = conn.execute(
            "SELECT * FROM ideas WHERE status = ? ORDER BY id DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM ideas ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def get_idea(conn: sqlite3.Connection, idea_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Agent outputs
# ---------------------------------------------------------------------------


def save_agent_output(conn: sqlite3.Connection, idea_id: int, agent_name: str, output: dict) -> int:
    cur = conn.execute(
        "INSERT INTO agent_outputs (idea_id, agent_name, output_json) VALUES (?, ?, ?)",
        (idea_id, agent_name, json.dumps(output)),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def get_agent_outputs(conn: sqlite3.Connection, idea_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM agent_outputs WHERE idea_id = ? ORDER BY id", (idea_id,)
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["output"] = json.loads(d["output_json"])
        results.append(d)
    return results


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


def save_feedback(conn: sqlite3.Connection, idea_id: int, feedback: dict) -> int:
    cur = conn.execute(
        "INSERT INTO feedback (idea_id, decision, rating, tags, note) VALUES (?, ?, ?, ?, ?)",
        (
            idea_id,
            feedback["decision"],
            feedback["rating"],
            json.dumps(feedback.get("tags", [])),
            feedback.get("note", ""),
        ),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def update_feedback(conn: sqlite3.Connection, idea_id: int, updates: dict[str, Any]) -> None:
    """Upsert feedback for a given idea.

    If a feedback row already exists for *idea_id*, merge *updates* into it.
    Otherwise insert a new row with the provided fields.
    """
    existing = conn.execute(
        "SELECT id, decision, rating, tags, note FROM feedback"
        " WHERE idea_id = ? ORDER BY id DESC LIMIT 1",
        (idea_id,),
    ).fetchone()

    if existing:
        row = dict(existing)
        decision = updates.get("decision", row["decision"])
        rating = updates.get("rating", row["rating"])
        tags_raw = row["tags"]
        current_tags: list[str] = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
        if "tags" in updates:
            current_tags = list(set(current_tags) | set(updates["tags"]))
        note = updates.get("note", row["note"])
        conn.execute(
            "UPDATE feedback SET decision = ?, rating = ?, tags = ?, note = ? WHERE id = ?",
            (decision, rating, json.dumps(current_tags), note, row["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO feedback (idea_id, decision, rating, tags, note) VALUES (?, ?, ?, ?, ?)",
            (
                idea_id,
                updates.get("decision", "meh"),
                updates.get("rating", 5),
                json.dumps(updates.get("tags", [])),
                updates.get("note", ""),
            ),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


def load_preferences(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("SELECT key, value_json FROM preferences").fetchall()
    return {r["key"]: json.loads(r["value_json"]) for r in rows}


def save_preference(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """INSERT INTO preferences (key, value_json, updated_at)
           VALUES (?, ?, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json,
                                          updated_at = excluded.updated_at""",
        (key, json.dumps(value)),
    )
    conn.commit()


def reset_preferences(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM preferences")
    conn.commit()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def save_session(
    conn: sqlite3.Connection,
    region: str,
    domains: list[str],
    constraints: str,
) -> int:
    """Insert a new session row and return its id."""
    cur = conn.execute(
        "INSERT INTO sessions (region, domains, constraints) VALUES (?, ?, ?)",
        (region, json.dumps(domains), constraints),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def get_latest_session(conn: sqlite3.Connection) -> dict | None:
    """Return the most recent session, or None."""
    row = conn.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return None
    d = dict(row)
    d["domains"] = json.loads(d["domains"])
    return d


def update_session_progress(
    conn: sqlite3.Connection,
    session_id: int,
    loop_num: int,
    total_winners: int,
) -> None:
    """Persist loop progress for the given session."""
    conn.execute(
        "UPDATE sessions SET loop_num = ?, total_winners = ?,"
        " updated_at = datetime('now') WHERE id = ?",
        (loop_num, total_winners, session_id),
    )
    conn.commit()


def get_recent_rejections(conn: sqlite3.Connection, session_id: int) -> list[dict]:
    """Return names + concept summaries of killed ideas created after the session started."""
    rows = conn.execute(
        """SELECT i.name, ic.concept_summary
           FROM ideas i
           JOIN sessions s ON s.id = ?
           LEFT JOIN idea_concepts ic ON ic.idea_id = i.id
           WHERE i.status = 'killed' AND i.created_at >= s.created_at
           ORDER BY i.id DESC""",
        (session_id,),
    ).fetchall()
    return [{"name": r["name"], "concept_summary": r["concept_summary"] or ""} for r in rows]


# ---------------------------------------------------------------------------
# Idea concepts (rejection memory)
# ---------------------------------------------------------------------------


def save_concept(
    conn: sqlite3.Connection,
    idea_id: int,
    concept_summary: str,
    problem_domain: str = "",
    rejection_source: str = "",
) -> int:
    """Insert a concept fingerprint for an idea and return its id."""
    cur = conn.execute(
        """INSERT INTO idea_concepts (idea_id, concept_summary, problem_domain, rejection_source)
           VALUES (?, ?, ?, ?)""",
        (idea_id, concept_summary, problem_domain, rejection_source),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def get_rejected_concepts(conn: sqlite3.Connection, limit: int = 30) -> list[dict]:
    """Return concept summaries from ALL sessions (cross-session memory)."""
    rows = conn.execute(
        """SELECT i.name, ic.concept_summary, ic.problem_domain, ic.rejection_source
           FROM idea_concepts ic
           JOIN ideas i ON i.id = ic.idea_id
           ORDER BY ic.id DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def get_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) AS c FROM ideas").fetchone()["c"]
    by_status: dict[str, int] = {}
    for row in conn.execute("SELECT status, COUNT(*) AS c FROM ideas GROUP BY status"):
        by_status[row["status"]] = row["c"]
    avg_score = conn.execute(
        "SELECT AVG(composite_score) AS a FROM ideas WHERE composite_score IS NOT NULL"
    ).fetchone()["a"]
    feedback_count = conn.execute("SELECT COUNT(*) AS c FROM feedback").fetchone()["c"]
    return {
        "total_ideas": total,
        "by_status": by_status,
        "avg_composite_score": round(avg_score, 2) if avg_score else None,
        "total_feedback": feedback_count,
    }


# ---------------------------------------------------------------------------
# Token usage / cost tracking
# ---------------------------------------------------------------------------


def save_token_usage(
    conn: sqlite3.Connection,
    idea_id: int | None,
    agent_name: str,
    input_tokens: int,
    output_tokens: int,
    provider: str = "",
    model: str = "",
) -> None:
    """Record token usage for one agent call."""
    conn.execute(
        """INSERT INTO token_usage
           (idea_id, agent_name, input_tokens, output_tokens, provider, model)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (idea_id, agent_name, input_tokens, output_tokens, provider, model),
    )
    conn.commit()


def get_cost_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Aggregate token usage across all calls."""
    totals = conn.execute(
        "SELECT SUM(input_tokens) AS ti, SUM(output_tokens) AS to_ FROM token_usage"
    ).fetchone()
    by_agent: list[dict] = []
    for row in conn.execute(
        """SELECT agent_name,
                  SUM(input_tokens) AS input_tokens,
                  SUM(output_tokens) AS output_tokens,
                  COUNT(*) AS calls
           FROM token_usage
           GROUP BY agent_name
           ORDER BY (SUM(input_tokens) + SUM(output_tokens)) DESC"""
    ):
        by_agent.append(dict(row))

    by_model: list[dict] = []
    for row in conn.execute(
        """SELECT provider, model,
                  SUM(input_tokens) AS input_tokens,
                  SUM(output_tokens) AS output_tokens,
                  COUNT(*) AS calls
           FROM token_usage
           WHERE provider != ''
           GROUP BY provider, model"""
    ):
        by_model.append(dict(row))

    return {
        "total_input_tokens": totals["ti"] or 0,
        "total_output_tokens": totals["to_"] or 0,
        "by_agent": by_agent,
        "by_model": by_model,
    }


# ---------------------------------------------------------------------------
# Scoreboard persistence
# ---------------------------------------------------------------------------


def save_scoreboard_entry(conn: sqlite3.Connection, entry: dict) -> None:
    """Upsert a scoreboard entry."""
    conn.execute(
        """INSERT INTO scoreboard
           (idea_name, composite_score, verdict, taste_decision, taste_rating)
           VALUES (?, ?, ?, ?, ?)""",
        (
            entry.get("name", ""),
            entry.get("composite_score", 0),
            entry.get("verdict", ""),
            entry.get("taste_decision", ""),
            entry.get("taste_rating", 0),
        ),
    )
    conn.commit()


def get_scoreboard(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """Return top scoreboard entries."""
    rows = conn.execute(
        "SELECT * FROM scoreboard ORDER BY composite_score DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]

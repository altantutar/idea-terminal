"""Tests for database connection, schema, and CRUD operations."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from idea_factory.db import repository as repo
from idea_factory.db.connection import get_db


@pytest.fixture
def db_conn():
    """Create a temporary database for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = get_db(db_path)
        yield conn
        conn.close()


class TestConnection:
    def test_creates_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "subdir" / "test.db"
            conn = get_db(db_path)
            assert db_path.exists()
            conn.close()

    def test_schema_tables_exist(self, db_conn):
        tables = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {row["name"] for row in tables}
        assert "ideas" in table_names
        assert "agent_outputs" in table_names
        assert "feedback" in table_names
        assert "preferences" in table_names
        assert "sessions" in table_names
        assert "token_usage" in table_names
        assert "scoreboard" in table_names

    def test_idempotent_schema(self):
        """Calling get_db twice on the same file should not error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn1 = get_db(db_path)
            conn1.close()
            conn2 = get_db(db_path)
            conn2.close()


class TestIdeaCRUD:
    def test_save_and_get_idea(self, db_conn):
        idea = {
            "name": "TestIdea",
            "one_liner": "A test",
            "domain": "saas",
            "problem": "Testing",
            "solution": "Automate",
            "target_user": "Devs",
            "monetization": "Sub",
            "region": "Global",
            "tags": ["test"],
        }
        idea_id = repo.save_idea(db_conn, idea)
        assert idea_id > 0

        fetched = repo.get_idea(db_conn, idea_id)
        assert fetched is not None
        assert fetched["name"] == "TestIdea"
        assert fetched["domain"] == "saas"

    def test_get_nonexistent_idea(self, db_conn):
        assert repo.get_idea(db_conn, 99999) is None

    def test_update_idea_status(self, db_conn):
        idea_id = repo.save_idea(db_conn, {
            "name": "X", "one_liner": "Y", "domain": "d",
            "problem": "p", "solution": "s", "target_user": "u",
            "monetization": "m", "region": "r", "tags": [],
        })
        repo.update_idea_status(db_conn, idea_id, "winner", 8.5)
        fetched = repo.get_idea(db_conn, idea_id)
        assert fetched["status"] == "winner"
        assert fetched["composite_score"] == 8.5

    def test_list_ideas(self, db_conn):
        for name in ["A", "B", "C"]:
            repo.save_idea(db_conn, {
                "name": name, "one_liner": "Y", "domain": "d",
                "problem": "p", "solution": "s", "target_user": "u",
                "monetization": "m", "region": "r", "tags": [],
            })
        ideas = repo.list_ideas(db_conn)
        assert len(ideas) == 3

    def test_list_ideas_by_status(self, db_conn):
        id1 = repo.save_idea(db_conn, {
            "name": "A", "one_liner": "Y", "domain": "d",
            "problem": "p", "solution": "s", "target_user": "u",
            "monetization": "m", "region": "r", "tags": [],
        })
        repo.update_idea_status(db_conn, id1, "winner")
        repo.save_idea(db_conn, {
            "name": "B", "one_liner": "Y", "domain": "d",
            "problem": "p", "solution": "s", "target_user": "u",
            "monetization": "m", "region": "r", "tags": [],
        })
        winners = repo.list_ideas(db_conn, "winner")
        assert len(winners) == 1
        assert winners[0]["name"] == "A"


class TestAgentOutputs:
    def test_save_and_get(self, db_conn):
        idea_id = repo.save_idea(db_conn, {
            "name": "X", "one_liner": "Y", "domain": "d",
            "problem": "p", "solution": "s", "target_user": "u",
            "monetization": "m", "region": "r", "tags": [],
        })
        repo.save_agent_output(db_conn, idea_id, "challenger", {"verdict": "SURVIVE"})
        repo.save_agent_output(db_conn, idea_id, "builder", {"buildable": True})

        outputs = repo.get_agent_outputs(db_conn, idea_id)
        assert len(outputs) == 2
        assert outputs[0]["agent_name"] == "challenger"
        assert outputs[0]["output"]["verdict"] == "SURVIVE"


class TestFeedback:
    def test_save_feedback(self, db_conn):
        idea_id = repo.save_idea(db_conn, {
            "name": "X", "one_liner": "Y", "domain": "d",
            "problem": "p", "solution": "s", "target_user": "u",
            "monetization": "m", "region": "r", "tags": [],
        })
        fb_id = repo.save_feedback(db_conn, idea_id, {
            "decision": "love",
            "rating": 9,
            "tags": ["ai"],
            "note": "Great!",
        })
        assert fb_id > 0


class TestPreferences:
    def test_save_and_load(self, db_conn):
        repo.save_preference(db_conn, "domain_weights", {"saas": 2.0})
        prefs = repo.load_preferences(db_conn)
        assert prefs["domain_weights"] == {"saas": 2.0}

    def test_upsert(self, db_conn):
        repo.save_preference(db_conn, "key1", {"a": 1})
        repo.save_preference(db_conn, "key1", {"a": 2})
        prefs = repo.load_preferences(db_conn)
        assert prefs["key1"] == {"a": 2}

    def test_reset(self, db_conn):
        repo.save_preference(db_conn, "key1", "val1")
        repo.reset_preferences(db_conn)
        prefs = repo.load_preferences(db_conn)
        assert prefs == {}


class TestSessions:
    def test_save_and_get_latest(self, db_conn):
        sid = repo.save_session(db_conn, "US", ["saas", "ai"], "solo founder")
        assert sid > 0

        latest = repo.get_latest_session(db_conn)
        assert latest is not None
        assert latest["region"] == "US"
        assert latest["domains"] == ["saas", "ai"]
        assert latest["constraints"] == "solo founder"

    def test_update_progress(self, db_conn):
        sid = repo.save_session(db_conn, "Global", ["fintech"], "")
        repo.update_session_progress(db_conn, sid, loop_num=3, total_winners=2)
        latest = repo.get_latest_session(db_conn)
        assert latest["loop_num"] == 3
        assert latest["total_winners"] == 2

    def test_no_session(self, db_conn):
        assert repo.get_latest_session(db_conn) is None


class TestTokenUsage:
    def test_save_and_get_summary(self, db_conn):
        idea_id = repo.save_idea(db_conn, {
            "name": "X", "one_liner": "Y", "domain": "d",
            "problem": "p", "solution": "s", "target_user": "u",
            "monetization": "m", "region": "r", "tags": [],
        })
        repo.save_token_usage(db_conn, idea_id, "creator", 100, 50, "anthropic", "claude-sonnet")
        repo.save_token_usage(db_conn, idea_id, "challenger", 200, 80, "anthropic", "claude-sonnet")

        summary = repo.get_cost_summary(db_conn)
        assert summary["total_input_tokens"] == 300
        assert summary["total_output_tokens"] == 130
        assert len(summary["by_agent"]) == 2
        assert len(summary["by_model"]) == 1

    def test_empty_usage(self, db_conn):
        summary = repo.get_cost_summary(db_conn)
        assert summary["total_input_tokens"] == 0
        assert summary["total_output_tokens"] == 0


class TestScoreboard:
    def test_save_and_get(self, db_conn):
        repo.save_scoreboard_entry(db_conn, {
            "name": "Idea1",
            "composite_score": 8.5,
            "verdict": "WINNER",
            "taste_decision": "love",
            "taste_rating": 9,
        })
        repo.save_scoreboard_entry(db_conn, {
            "name": "Idea2",
            "composite_score": 6.0,
            "verdict": "CONTENDER",
            "taste_decision": "like",
            "taste_rating": 7,
        })

        board = repo.get_scoreboard(db_conn, limit=10)
        assert len(board) == 2
        # Sorted by composite_score desc
        assert board[0]["idea_name"] == "Idea1"
        assert board[1]["idea_name"] == "Idea2"

    def test_empty_scoreboard(self, db_conn):
        board = repo.get_scoreboard(db_conn)
        assert board == []


class TestStats:
    def test_basic_stats(self, db_conn):
        for name, status in [("A", "winner"), ("B", "killed"), ("C", "killed")]:
            idea_id = repo.save_idea(db_conn, {
                "name": name, "one_liner": "Y", "domain": "d",
                "problem": "p", "solution": "s", "target_user": "u",
                "monetization": "m", "region": "r", "tags": [],
            })
            score = 8.0 if status == "winner" else None
            repo.update_idea_status(db_conn, idea_id, status, score)

        stats = repo.get_stats(db_conn)
        assert stats["total_ideas"] == 3
        assert stats["by_status"]["winner"] == 1
        assert stats["by_status"]["killed"] == 2
        assert stats["avg_composite_score"] == 8.0

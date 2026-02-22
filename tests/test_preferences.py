"""Tests for preference learning logic."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from idea_factory.db.connection import get_db
from idea_factory.preferences import (
    PreferenceState,
    build_taste_prefix,
    load_preferences,
    save_preferences,
    update_preferences,
)


@pytest.fixture
def db_conn():
    with tempfile.TemporaryDirectory() as tmpdir:
        conn = get_db(Path(tmpdir) / "test.db")
        yield conn
        conn.close()


class TestPreferenceState:
    def test_default_state(self):
        state = PreferenceState()
        assert state.domain_weights == {}
        assert state.reject_tag_weights == {}
        assert state.channel_weights == {}
        assert state.hard_nos == []
        assert state.archetype_weights == {}


class TestUpdatePreferences:
    def test_love_increases_domain_weight(self):
        prefs = PreferenceState()
        idea = {"domain": "fintech", "tags": ["payments"]}
        feedback = {"decision": "love", "rating": 9}
        prefs = update_preferences(prefs, feedback, idea)
        assert prefs.domain_weights["fintech"] == 2.0

    def test_hate_decreases_domain_weight(self):
        prefs = PreferenceState()
        idea = {"domain": "social", "tags": []}
        feedback = {"decision": "hate", "rating": 2}
        prefs = update_preferences(prefs, feedback, idea)
        assert prefs.domain_weights["social"] == -2.0

    def test_hate_adds_hard_no(self):
        prefs = PreferenceState()
        idea = {"name": "BadIdea", "domain": "d", "tags": []}
        feedback = {"decision": "hate", "rating": 1}
        prefs = update_preferences(prefs, feedback, idea)
        assert any(
            (item["name"] if isinstance(item, dict) else item) == "BadIdea"
            for item in prefs.hard_nos
        )

    def test_like_reduces_reject_tags(self):
        prefs = PreferenceState(reject_tag_weights={"blockchain": 3.0})
        idea = {"domain": "d", "tags": ["blockchain"]}
        feedback = {"decision": "like", "rating": 7}
        prefs = update_preferences(prefs, feedback, idea)
        assert prefs.reject_tag_weights["blockchain"] == 2.0

    def test_meh_increases_reject_tags(self):
        prefs = PreferenceState()
        idea = {"domain": "d", "tags": ["nft"]}
        feedback = {"decision": "meh", "rating": 3}
        prefs = update_preferences(prefs, feedback, idea)
        assert prefs.reject_tag_weights["nft"] == 0.5

    def test_archetype_weight_from_judge(self):
        prefs = PreferenceState()
        idea = {"domain": "d", "tags": []}
        feedback = {"decision": "love", "rating": 10}
        judge = {"archetype": "marketplace"}
        prefs = update_preferences(prefs, feedback, idea, judge)
        assert prefs.archetype_weights["marketplace"] == 2.0

    def test_cumulative_weights(self):
        prefs = PreferenceState()
        idea = {"domain": "saas", "tags": []}
        for _ in range(3):
            prefs = update_preferences(prefs, {"decision": "like", "rating": 7}, idea)
        assert prefs.domain_weights["saas"] == 3.0

    def test_no_duplicate_hard_nos(self):
        prefs = PreferenceState()
        idea = {"name": "X", "domain": "d", "tags": []}
        fb = {"decision": "hate", "rating": 1}
        prefs = update_preferences(prefs, fb, idea)
        prefs = update_preferences(prefs, fb, idea)
        names = [(item["name"] if isinstance(item, dict) else item) for item in prefs.hard_nos]
        assert names.count("X") == 1


class TestBuildTastePrefix:
    def test_empty_state_returns_empty(self):
        prefs = PreferenceState()
        assert build_taste_prefix(prefs) == ""

    def test_includes_preferred_domains(self):
        prefs = PreferenceState(domain_weights={"fintech": 3.0, "ai": 1.0})
        prefix = build_taste_prefix(prefs)
        assert "Preferred domains" in prefix
        assert "fintech" in prefix

    def test_includes_avoided_domains(self):
        prefs = PreferenceState(domain_weights={"social": -2.0})
        prefix = build_taste_prefix(prefs)
        assert "Avoid domains" in prefix
        assert "social" in prefix

    def test_includes_bad_tags(self):
        prefs = PreferenceState(reject_tag_weights={"nft": 5.0})
        prefix = build_taste_prefix(prefs)
        assert "Avoid tags" in prefix
        assert "nft" in prefix

    def test_includes_archetypes(self):
        prefs = PreferenceState(archetype_weights={"marketplace": 2.0})
        prefix = build_taste_prefix(prefs)
        assert "Preferred idea archetypes" in prefix
        assert "marketplace" in prefix


class TestPersistence:
    def test_save_and_load_round_trip(self, db_conn):
        prefs = PreferenceState(
            domain_weights={"saas": 2.0},
            reject_tag_weights={"nft": 1.0},
            hard_nos=["BadIdea"],
        )
        save_preferences(db_conn, prefs)

        loaded = load_preferences(db_conn)
        assert loaded.domain_weights == {"saas": 2.0}
        assert loaded.reject_tag_weights == {"nft": 1.0}
        assert loaded.hard_nos == ["BadIdea"]

    def test_load_empty_db(self, db_conn):
        loaded = load_preferences(db_conn)
        assert loaded.domain_weights == {}
        assert loaded.hard_nos == []

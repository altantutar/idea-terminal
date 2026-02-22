"""Tests for Pydantic models — schema validation and edge cases."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from idea_factory.models import (
    BuilderOutput,
    ChallengerOutput,
    ClaudeCheckOutput,
    ConsumerOutput,
    CreatorOutput,
    DistributorOutput,
    IdeaSchema,
    InspirationSourceSchema,
    JudgeOutput,
    JudgeScores,
    ReflectionOutput,
    TasteFeedback,
    UserFeedback,
)


class TestIdeaSchema:
    def test_valid_idea(self):
        idea = IdeaSchema(
            name="TestApp",
            one_liner="A test application",
            domain="saas",
            problem="Testing is hard",
            solution="Automate it",
            target_user="Developers",
            monetization="SaaS subscription",
            region="Global",
            tags=["testing", "automation"],
        )
        assert idea.name == "TestApp"
        assert idea.tags == ["testing", "automation"]

    def test_default_tags(self):
        idea = IdeaSchema(
            name="X",
            one_liner="Y",
            domain="d",
            problem="p",
            solution="s",
            target_user="u",
            monetization="m",
            region="r",
        )
        assert idea.tags == []

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            IdeaSchema(name="X", one_liner="Y")  # type: ignore[call-arg]

    def test_default_inspired_by(self):
        idea = IdeaSchema(
            name="X",
            one_liner="Y",
            domain="d",
            problem="p",
            solution="s",
            target_user="u",
            monetization="m",
            region="r",
        )
        assert idea.inspired_by == []

    def test_inspired_by_with_sources(self):
        idea = IdeaSchema(
            name="TestApp",
            one_liner="A test application",
            domain="saas",
            problem="Testing is hard",
            solution="Automate it",
            target_user="Developers",
            monetization="SaaS subscription",
            region="Global",
            tags=["testing"],
            inspired_by=[
                InspirationSourceSchema(
                    title="HN: New testing framework",
                    url="https://news.ycombinator.com/item?id=123",
                    platform="Hacker News",
                ),
                InspirationSourceSchema(
                    title="Product Hunt launch",
                    url="https://producthunt.com/posts/test",
                    platform="Product Hunt",
                ),
            ],
        )
        assert len(idea.inspired_by) == 2
        assert idea.inspired_by[0].platform == "Hacker News"
        assert idea.inspired_by[1].url == "https://producthunt.com/posts/test"


class TestInspirationSourceSchema:
    def test_valid_source(self):
        src = InspirationSourceSchema(
            title="Test Article",
            url="https://example.com/article",
            platform="TechCrunch",
        )
        assert src.title == "Test Article"
        assert src.url == "https://example.com/article"
        assert src.platform == "TechCrunch"

    def test_defaults(self):
        src = InspirationSourceSchema(title="Just a title")
        assert src.title == "Just a title"
        assert src.url == ""
        assert src.platform == ""


class TestCreatorOutput:
    def test_valid(self):
        out = CreatorOutput(
            ideas=[
                IdeaSchema(
                    name="A",
                    one_liner="B",
                    domain="d",
                    problem="p",
                    solution="s",
                    target_user="u",
                    monetization="m",
                    region="r",
                )
            ]
        )
        assert len(out.ideas) == 1

    def test_empty_ideas(self):
        out = CreatorOutput(ideas=[])
        assert out.ideas == []


class TestChallengerOutput:
    def test_kill_verdict(self):
        out = ChallengerOutput(
            verdict="KILL",
            fatal_flaws=["No market"],
            risks=["Competitor risk"],
        )
        assert out.verdict == "KILL"
        assert len(out.fatal_flaws) == 1

    def test_survive_verdict(self):
        out = ChallengerOutput(
            verdict="SURVIVE",
            survival_reason="Strong moat",
        )
        assert out.verdict == "SURVIVE"
        assert out.fatal_flaws == []


class TestBuilderOutput:
    def test_buildable(self):
        out = BuilderOutput(
            buildable=True,
            mvp_scope="Basic CRUD app",
            build_risk="API rate limits",
        )
        assert out.buildable is True
        assert out.tech_stack == []
        assert out.milestones == []


class TestDistributorOutput:
    def test_basic(self):
        out = DistributorOutput(
            primary_channel="Twitter",
            viral_hook="Share results",
        )
        assert out.primary_channel == "Twitter"
        assert out.channels == []


class TestConsumerOutput:
    def test_scores_in_range(self):
        out = ConsumerOutput(
            overall_excitement=7,
            willingness_to_pay=5,
        )
        assert 1 <= out.overall_excitement <= 10
        assert 1 <= out.willingness_to_pay <= 10

    def test_score_out_of_range(self):
        with pytest.raises(ValidationError):
            ConsumerOutput(overall_excitement=0, willingness_to_pay=5)

        with pytest.raises(ValidationError):
            ConsumerOutput(overall_excitement=5, willingness_to_pay=11)


class TestJudgeOutput:
    def test_valid(self):
        out = JudgeOutput(
            scores=JudgeScores(
                novelty=8,
                feasibility=7,
                market_potential=9,
                defensibility=6,
                excitement=8,
            ),
            composite_score=7.5,
            verdict="WINNER",
            one_line_summary="Great idea",
        )
        assert out.composite_score == 7.5
        assert out.verdict == "WINNER"

    def test_score_out_of_range(self):
        with pytest.raises(ValidationError):
            JudgeScores(
                novelty=11,
                feasibility=7,
                market_potential=9,
                defensibility=6,
                excitement=8,
            )


class TestUserFeedback:
    def test_valid(self):
        fb = UserFeedback(decision="love", rating=9, tags=["ai"])
        assert fb.decision == "love"
        assert fb.rating == 9

    def test_rating_bounds(self):
        with pytest.raises(ValidationError):
            UserFeedback(decision="like", rating=0)
        with pytest.raises(ValidationError):
            UserFeedback(decision="like", rating=11)


class TestTasteFeedback:
    def test_valid(self):
        fb = TasteFeedback(decision="meh", rating=4, note="Not exciting")
        assert fb.decision == "meh"


class TestClaudeCheckOutput:
    def test_valid(self):
        out = ClaudeCheckOutput(
            verdict="one_shottable",
            claude_product="Claude Code",
            time_estimate="~2 hours",
            what_it_builds="Full MVP",
            what_it_cant="Distribution",
            defensibility_note="Low moat",
        )
        assert out.verdict == "one_shottable"


class TestReflectionOutput:
    def test_satisfactory(self):
        out = ReflectionOutput(is_satisfactory=True)
        assert out.critique == ""
        assert out.weaknesses == []

    def test_unsatisfactory(self):
        out = ReflectionOutput(
            is_satisfactory=False,
            critique="Too generic",
            weaknesses=["Vague problem statement"],
            suggested_focus="Be more specific",
        )
        assert not out.is_satisfactory
        assert len(out.weaknesses) == 1

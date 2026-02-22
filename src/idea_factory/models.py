"""Pydantic models for all structured data in the pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Inspiration source for attribution
# ---------------------------------------------------------------------------


class InspirationSourceSchema(BaseModel):
    """A source that inspired a startup idea."""

    title: str = Field(description="Title of the source article/post")
    url: str = Field(default="", description="URL of the source")
    platform: str = Field(default="", description="Platform name (e.g. Product Hunt, HN)")


# ---------------------------------------------------------------------------
# Creator output
# ---------------------------------------------------------------------------


class IdeaSchema(BaseModel):
    """A single startup idea produced by the Creator agent."""

    name: str = Field(description="Short punchy name for the idea")
    one_liner: str = Field(description="One sentence elevator pitch")
    domain: str = Field(description="Primary domain (e.g. fintech, healthtech)")
    problem: str = Field(description="The problem being solved")
    solution: str = Field(description="How the product solves it")
    target_user: str = Field(description="Who is the primary user")
    monetization: str = Field(description="Revenue model")
    region: str = Field(description="Target region/market")
    tags: list[str] = Field(default_factory=list, description="Keyword tags")
    inspired_by: list[InspirationSourceSchema] = Field(
        default_factory=list, description="Sources that inspired this idea"
    )


class CreatorOutput(BaseModel):
    """Batch output from the Creator agent."""

    ideas: list[IdeaSchema]


# ---------------------------------------------------------------------------
# Challenger output
# ---------------------------------------------------------------------------


class ChallengerOutput(BaseModel):
    """Output from the Challenger agent — stress-tests the idea."""

    verdict: str = Field(description="KILL or SURVIVE")
    fatal_flaws: list[str] = Field(default_factory=list, description="Deal-breaking issues")
    risks: list[str] = Field(default_factory=list, description="Significant but non-fatal risks")
    competitor_overlap: str = Field(default="", description="Existing competitors / overlap")
    survival_reason: str = Field(default="", description="Why the idea survives (if it does)")


# ---------------------------------------------------------------------------
# Builder output
# ---------------------------------------------------------------------------


class MilestoneItem(BaseModel):
    week: str
    goal: str


class StackItem(BaseModel):
    layer: str
    choice: str


class BuilderOutput(BaseModel):
    """Output from the Builder agent — feasibility & build plan."""

    buildable: bool = Field(description="Can this be built by a small team in 8 weeks?")
    tech_stack: list[StackItem] = Field(default_factory=list)
    mvp_scope: str = Field(default="", description="What the MVP includes")
    milestones: list[MilestoneItem] = Field(default_factory=list)
    build_risk: str = Field(default="", description="Biggest technical risk")


# ---------------------------------------------------------------------------
# Distributor output
# ---------------------------------------------------------------------------


class ChannelItem(BaseModel):
    channel: str
    tactic: str
    expected_cac: str = ""


class DistributorOutput(BaseModel):
    """Output from the Distributor agent — go-to-market plan."""

    primary_channel: str = Field(description="Main distribution channel")
    channels: list[ChannelItem] = Field(default_factory=list)
    viral_hook: str = Field(default="", description="What makes users share this")
    launch_strategy: str = Field(default="", description="Day-1 launch plan")
    moat: str = Field(default="", description="Defensibility / network effects")


# ---------------------------------------------------------------------------
# Consumer output
# ---------------------------------------------------------------------------


class PersonaReaction(BaseModel):
    persona: str
    reaction: str
    would_pay: bool = False
    objection: str = ""


class ConsumerOutput(BaseModel):
    """Output from the Consumer agent — simulated user reactions."""

    personas: list[PersonaReaction] = Field(default_factory=list)
    overall_excitement: int = Field(ge=1, le=10, description="1-10 excitement score")
    willingness_to_pay: int = Field(ge=1, le=10, description="1-10 WTP score")
    key_objection: str = Field(default="", description="Most common objection")


# ---------------------------------------------------------------------------
# Judge output
# ---------------------------------------------------------------------------


class JudgeScores(BaseModel):
    novelty: int = Field(ge=1, le=10)
    feasibility: int = Field(ge=1, le=10)
    market_potential: int = Field(ge=1, le=10)
    defensibility: int = Field(ge=1, le=10)
    excitement: int = Field(ge=1, le=10)


class JudgeOutput(BaseModel):
    """Output from the Judge agent — final scoring and verdict."""

    scores: JudgeScores
    composite_score: float = Field(ge=0, le=10, description="Weighted composite")
    verdict: str = Field(description="WINNER / CONTENDER / PASS")
    one_line_summary: str = Field(default="", description="Why this verdict")
    archetype: str = Field(default="", description="Idea archetype tag")


# ---------------------------------------------------------------------------
# User feedback
# ---------------------------------------------------------------------------


class UserFeedback(BaseModel):
    """Structured feedback the user gives after reviewing an idea."""

    decision: str = Field(description="love | like | meh | hate")
    rating: int = Field(ge=1, le=10, description="Overall rating 1-10")
    tags: list[str] = Field(default_factory=list, description="Tags user liked/disliked")
    note: str = Field(default="", description="Free-form note")


class TasteFeedback(BaseModel):
    """AI-generated feedback from the Taste Agent (replaces human in livestream mode)."""

    decision: str = Field(description="love | like | meh | hate")
    rating: int = Field(ge=1, le=10, description="Overall rating 1-10")
    tags: list[str] = Field(default_factory=list, description="Tags the persona liked/disliked")
    note: str = Field(default="", description="Persona's rationale")


# ---------------------------------------------------------------------------
# Claude Check output
# ---------------------------------------------------------------------------


class ClaudeCheckOutput(BaseModel):
    """Output from the Claude Check agent — can Claude one-shot this?"""

    verdict: str = Field(description="one_shottable / needs_work / not_feasible")
    claude_product: str = Field(
        description="Which Claude product could do it (e.g. Claude Code, Claude Chat + Artifacts)"
    )
    time_estimate: str = Field(description="e.g. ~2 hours, ~1 day, not applicable")
    what_it_builds: str = Field(description="What Claude could produce in one session")
    what_it_cant: str = Field(
        description="What remains unsolved (data moat, distribution, regulatory, infra)"
    )
    defensibility_note: str = Field(description="Implication for the startup's moat")


# ---------------------------------------------------------------------------
# Reflection output
# ---------------------------------------------------------------------------


class ReflectionOutput(BaseModel):
    """Critique of an agent's output from a reflection step."""

    is_satisfactory: bool = Field(description="True if the output meets quality standards")
    critique: str = Field(default="", description="What is wrong or could be improved")
    weaknesses: list[str] = Field(default_factory=list, description="Specific weaknesses found")
    suggested_focus: str = Field(default="", description="What to focus on when re-evaluating")

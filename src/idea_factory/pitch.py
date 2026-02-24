"""Pitch evaluation orchestrator — evaluate a user-submitted startup idea."""

from __future__ import annotations

import signal

from rich.panel import Panel
from rich.prompt import Prompt

from idea_factory.agents.builder import BuilderAgent
from idea_factory.agents.challenger import ChallengerAgent
from idea_factory.agents.claude_check import ClaudeCheckAgent
from idea_factory.agents.consumer import ConsumerAgent
from idea_factory.agents.distributor import DistributorAgent
from idea_factory.agents.judge import JudgeAgent
from idea_factory.agents.refiner import RefinerAgent
from idea_factory.config import Settings
from idea_factory.db import repository as repo
from idea_factory.db.connection import get_db
from idea_factory.display import (
    agent_status,
    console,
    display_challenger_result,
    display_claude_check,
    display_idea_card,
    prompt_feedback,
    prompt_quick_feedback,
)
from idea_factory.llm.factory import get_provider
from idea_factory.preferences import (
    load_preferences,
    save_preferences,
    update_preferences,
)
from idea_factory.prompts import (
    challenger_reflection_prompt,
    judge_reflection_prompt,
)
from idea_factory.reflexion import run_with_reflexion


def _track_usage(conn, agent, idea_id, settings):
    """Persist token usage from the last agent call."""
    usage = agent.last_usage
    if usage:
        repo.save_token_usage(
            conn,
            idea_id=idea_id,
            agent_name=agent.name,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            provider=settings.llm_provider,
            model=settings.model,
        )


class _PitchExit(Exception):
    pass


def _handle_sigint(sig: int, frame: object) -> None:
    raise _PitchExit()


def run_pitch_evaluation(
    raw_pitch: str,
    settings: Settings,
    region: str = "Global",
    domain_hint: str = "",
    claude_check: bool = False,
    detailed_feedback: bool = True,
) -> None:
    """Evaluate a single user-submitted startup idea through the full pipeline."""
    conn = get_db(settings.db_path)
    provider = get_provider(settings)

    prev_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _handle_sigint)

    try:
        _run_pitch_inner(
            conn,
            provider,
            settings,
            raw_pitch,
            region,
            domain_hint,
            claude_check,
            detailed_feedback,
        )
    except _PitchExit:
        console.print("\n[yellow]Pitch evaluation interrupted.[/yellow]")
    finally:
        signal.signal(signal.SIGINT, prev_handler)
        conn.close()


def _run_pitch_inner(
    conn,
    provider,
    settings,
    raw_pitch,
    region,
    domain_hint,
    claude_check,
    detailed_feedback,
):
    """Inner logic for pitch evaluation, separated for clean try/finally."""
    # --- 1. REFINER — expand pitch into IdeaSchema ---
    refiner = RefinerAgent(provider)
    with agent_status("refiner"):
        idea_model = refiner.run(
            {
                "raw_pitch": raw_pitch,
                "region": region,
                "domain_hint": domain_hint,
            }
        )
    _track_usage(conn, refiner, None, settings)

    idea_dict = idea_model.model_dump()
    idea_dict["region"] = region  # ensure region is set

    # Show the expanded idea for confirmation
    console.print()
    console.print(
        Panel(
            f"[bold bright_white]{idea_dict['name']}[/bold bright_white]\n"
            f"[italic bright_cyan]{idea_dict.get('one_liner', '')}[/italic bright_cyan]\n\n"
            f"[bold]Domain:[/bold]       {idea_dict.get('domain', '')}\n"
            f"[bold]Problem:[/bold]      {idea_dict.get('problem', '')}\n"
            f"[bold]Solution:[/bold]     {idea_dict.get('solution', '')}\n"
            f"[bold]Target user:[/bold]  {idea_dict.get('target_user', '')}\n"
            f"[bold]Monetization:[/bold] {idea_dict.get('monetization', '')}\n"
            f"[bold]Why now:[/bold]      {idea_dict.get('why_now', '')}\n"
            f"[bold]Moat:[/bold]         {idea_dict.get('moat', '')}",
            title="[bold] Expanded Pitch [/bold]",
            title_align="left",
            border_style="bright_cyan",
            expand=False,
            width=76,
            padding=(1, 2),
        )
    )

    confirm = Prompt.ask(
        "\n  Proceed with evaluation?",
        choices=["y", "edit", "cancel"],
        default="y",
    )
    if confirm == "cancel":
        console.print("[dim]Pitch cancelled.[/dim]")
        return
    if confirm == "edit":
        console.print("[dim]Edit the expanded pitch fields:[/dim]")
        idea_dict["name"] = Prompt.ask("  Name", default=idea_dict["name"])
        idea_dict["one_liner"] = Prompt.ask("  One-liner", default=idea_dict.get("one_liner", ""))
        idea_dict["domain"] = Prompt.ask("  Domain", default=idea_dict.get("domain", ""))
        idea_dict["problem"] = Prompt.ask("  Problem", default=idea_dict.get("problem", ""))
        idea_dict["solution"] = Prompt.ask("  Solution", default=idea_dict.get("solution", ""))
        idea_dict["target_user"] = Prompt.ask(
            "  Target user", default=idea_dict.get("target_user", "")
        )
        idea_dict["monetization"] = Prompt.ask(
            "  Monetization", default=idea_dict.get("monetization", "")
        )

    # --- 2. SAVE — persist to DB with source='user' ---
    idea_id = repo.save_idea(conn, idea_dict, source="user")
    idea_dict["id"] = idea_id
    console.print(f"\n  [dim]Saved as idea #{idea_id}[/dim]")

    # --- 3. CHALLENGER (with reflexion) ---
    challenger = ChallengerAgent(provider)
    console.print()
    with agent_status("challenger"):
        ch_out = run_with_reflexion(
            agent=challenger,
            context={"idea": idea_dict},
            reflection_prompt_fn=lambda ctx, out: challenger_reflection_prompt(
                idea=ctx["idea"],
                challenger_output=out,
            ),
            max_rounds=settings.reflexion_max_rounds,
        )
    ch_dict = ch_out.model_dump()
    repo.save_agent_output(conn, idea_id, "challenger", ch_dict)
    _track_usage(conn, challenger, idea_id, settings)

    if ch_dict["verdict"] == "KILL":
        display_challenger_result(idea_dict["name"], survived=False)
        repo.update_idea_status(conn, idea_id, "killed")

        # Show fatal flaws so the user can iterate
        flaws = ch_dict.get("fatal_flaws", [])
        risks = ch_dict.get("risks", [])
        lines = ["[bold red]Your idea was killed by the Challenger.[/bold red]\n"]
        if flaws:
            lines.append("[bold]Fatal flaws:[/bold]")
            for f in flaws:
                lines.append(f"  [red]- {f}[/red]")
        if risks:
            lines.append("\n[bold]Risks:[/bold]")
            for r in risks:
                lines.append(f"  [yellow]- {r}[/yellow]")
        if ch_dict.get("competitor_overlap"):
            lines.append(f"\n[bold]Competitors:[/bold] {ch_dict['competitor_overlap']}")
        lines.append(f"\n[dim]Use 'idea-factory show {idea_id}' for full detail.[/dim]")

        console.print(
            Panel(
                "\n".join(lines),
                border_style="red",
                expand=False,
                width=76,
                padding=(1, 2),
            )
        )
        return

    display_challenger_result(
        idea_dict["name"],
        survived=True,
        one_liner=idea_dict.get("one_liner", ""),
    )
    console.print("\n  [bold bright_cyan]Advancing to full evaluation[/bold bright_cyan]\n")

    # --- 4. FULL PIPELINE: Builder -> Distributor -> Consumer -> Judge ---
    builder = BuilderAgent(provider)
    distributor = DistributorAgent(provider)
    consumer = ConsumerAgent(provider)
    judge = JudgeAgent(provider)

    # Builder
    with agent_status("builder"):
        b_out = builder.run({"idea": idea_dict})
    b_dict = b_out.model_dump()
    repo.save_agent_output(conn, idea_id, "builder", b_dict)
    _track_usage(conn, builder, idea_id, settings)

    if not b_dict.get("buildable", True):
        console.print("  [bold red]NOT BUILDABLE[/bold red] [dim]— evaluation stopped[/dim]")
        repo.update_idea_status(conn, idea_id, "unbuildable")
        console.print(f"\n[dim]Use 'idea-factory show {idea_id}' for full detail.[/dim]")
        return

    # Distributor
    with agent_status("distributor"):
        d_out = distributor.run({"idea": idea_dict, "build_output": b_dict})
    d_dict = d_out.model_dump()
    repo.save_agent_output(conn, idea_id, "distributor", d_dict)
    _track_usage(conn, distributor, idea_id, settings)

    # Consumer
    with agent_status("consumer"):
        c_out = consumer.run({"idea": idea_dict, "build_output": b_dict, "dist_output": d_dict})
    c_dict = c_out.model_dump()
    repo.save_agent_output(conn, idea_id, "consumer", c_dict)
    _track_usage(conn, consumer, idea_id, settings)

    # Judge (with reflexion)
    historical_concepts = repo.get_rejected_concepts(conn, limit=15)
    with agent_status("judge"):
        j_out = run_with_reflexion(
            agent=judge,
            context={
                "idea": idea_dict,
                "challenger_out": ch_dict,
                "builder_out": b_dict,
                "dist_out": d_dict,
                "consumer_out": c_dict,
                "historical_concepts": historical_concepts,
            },
            reflection_prompt_fn=lambda ctx, out: judge_reflection_prompt(
                idea=ctx["idea"],
                judge_output=out,
            ),
            max_rounds=settings.reflexion_max_rounds,
        )
    j_dict = j_out.model_dump()
    repo.save_agent_output(conn, idea_id, "judge", j_dict)
    _track_usage(conn, judge, idea_id, settings)

    # Update idea status
    verdict = j_dict.get("verdict", "PASS").lower()
    repo.update_idea_status(conn, idea_id, verdict, j_dict.get("composite_score"))

    # Display full idea card with scores
    display_idea_card(idea_dict, j_dict)

    # --- 5. CLAUDE CHECK (optional) ---
    if claude_check:
        claude_check_agent = ClaudeCheckAgent(provider)
        with agent_status("claude_check"):
            cc_out = claude_check_agent.run(
                {
                    "idea": idea_dict,
                    "judge_output": j_dict,
                    "builder_output": b_dict,
                }
            )
        cc_dict = cc_out.model_dump()
        repo.save_agent_output(conn, idea_id, "claude_check", cc_dict)
        _track_usage(conn, claude_check_agent, idea_id, settings)
        display_claude_check(idea_dict, cc_dict)

    # --- 6. FEEDBACK + PREFERENCES ---
    prefs = load_preferences(conn)
    if detailed_feedback:
        fb = prompt_feedback(idea_dict)
    else:
        fb_or_none = prompt_quick_feedback(idea_dict)
        if fb_or_none is None:
            # User chose "quit" — skip feedback, still show summary
            fb = {"decision": "meh", "rating": 5, "tags": [], "note": "skipped"}
        else:
            fb = fb_or_none
    repo.save_feedback(conn, idea_id, fb)
    prefs = update_preferences(prefs, fb, idea_dict, j_dict)
    save_preferences(conn, prefs)

    # --- 7. SUMMARY ---
    composite = j_dict.get("composite_score", 0)
    verdict_display = j_dict.get("verdict", "PASS")
    verdict_style = {
        "WINNER": "bold green",
        "CONTENDER": "bold yellow",
        "PASS": "bold red",
    }.get(verdict_display, "white")

    console.print(
        Panel(
            f"[bold]Idea:[/bold]      {idea_dict['name']}\n"
            f"[bold]Score:[/bold]     "
            f"[bold bright_white]{composite:.1f}[/bold bright_white]/10\n"
            f"[bold]Verdict:[/bold]   "
            f"[{verdict_style}]{verdict_display}[/{verdict_style}]\n\n"
            f"[dim]Run 'idea-factory show {idea_id}'"
            " for full agent outputs.[/dim]",
            title="[bold] Pitch Evaluation Complete [/bold]",
            title_align="left",
            border_style="bright_cyan",
            expand=False,
            width=76,
            padding=(1, 2),
        )
    )

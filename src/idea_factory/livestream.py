"""Autonomous livestream loop — AI taste agent replaces human feedback."""

from __future__ import annotations

import signal
import time

from rich.console import Console
from rich.panel import Panel

from idea_factory.agents.builder import BuilderAgent
from idea_factory.agents.challenger import ChallengerAgent
from idea_factory.agents.claude_check import ClaudeCheckAgent
from idea_factory.agents.consumer import ConsumerAgent
from idea_factory.agents.creator import CreatorAgent
from idea_factory.agents.distributor import DistributorAgent
from idea_factory.agents.judge import JudgeAgent
from idea_factory.agents.taste import TasteAgent
from idea_factory.config import Settings
from idea_factory.db import repository as repo
from idea_factory.db.connection import get_db
from idea_factory.display import (
    agent_status,
    console,
    display_challenger_result,
    display_claude_check,
    display_idea_card,
    display_loop_summary,
    display_scoreboard,
    display_taste_feedback,
)
from idea_factory.llm.factory import get_provider
from idea_factory.preferences import (
    build_taste_prefix,
    load_preferences,
    save_preferences,
    update_preferences,
)
from idea_factory.prompts import challenger_reflection_prompt, judge_reflection_prompt
from idea_factory.reflexion import run_with_reflexion
from idea_factory.trending import build_trending_prefix, fetch_trending

# Top-K survivors that proceed to full evaluation
TOP_K = 2

# Pacing between ideas (seconds)
PACE_BETWEEN_IDEAS = 2
PACE_BETWEEN_LOOPS = 5

# Auto-selected domains and region for autonomous mode
AUTO_DOMAINS = [
    "Software engineering",
    "Back-office automation",
    "Finance and accounting",
    "Data analysis and BI",
    "Cybersecurity",
    "E-commerce operations",
]
AUTO_REGION = "Global"
AUTO_CONSTRAINTS = "AI-native, can be built by a small team, high viral potential"


class GracefulExit(Exception):
    pass


def _handle_sigint(sig: int, frame: object) -> None:
    raise GracefulExit()


def run_livestream(
    settings: Settings,
    persona_label: str,
    persona_description: str,
    claude_check: bool = False,
) -> None:
    """Run the autonomous livestream loop — never stops until Ctrl+C."""
    conn = get_db(settings.db_path)
    provider = get_provider(settings)

    # Agents
    creator = CreatorAgent(provider)
    challenger = ChallengerAgent(provider)
    builder = BuilderAgent(provider)
    distributor = DistributorAgent(provider)
    consumer = ConsumerAgent(provider)
    judge = JudgeAgent(provider)
    taste = TasteAgent(provider)
    claude_check_agent = ClaudeCheckAgent(provider) if claude_check else None

    # State
    prefs = load_preferences(conn)
    recent_rejections: list[str] = []
    loop_num = 0
    scoreboard: list[dict] = []  # in-memory top-10

    # Graceful exit
    prev_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _handle_sigint)

    try:
        while True:
            loop_num += 1
            console.rule(f"[bold red]Livestream Loop {loop_num}[/bold red]")

            # ----- TRENDING CONTEXT -----
            console.print("  [dim]Fetching trending topics...[/dim]")
            trending_ctx = fetch_trending()
            trending_prefix = build_trending_prefix(trending_ctx)
            if trending_ctx.topics:
                console.print(
                    f"  [dim]{len(trending_ctx.topics)} trending signals loaded[/dim]\n"
                )

            # ----- CREATOR -----
            taste_prefix = build_taste_prefix(prefs)
            with agent_status("creator"):
                creator_out = creator.run({
                    "region": AUTO_REGION,
                    "domains": AUTO_DOMAINS,
                    "constraints": AUTO_CONSTRAINTS,
                    "taste_prefix": taste_prefix,
                    "recent_rejections": recent_rejections,
                    "trending_prefix": trending_prefix,
                })
            ideas = creator_out.ideas  # type: ignore[attr-defined]
            console.print(f"  [bold green]{len(ideas)} ideas generated[/bold green]\n")

            # Save ideas to DB
            idea_records: list[dict] = []
            for idea in ideas:
                idea_dict = idea.model_dump()
                idea_id = repo.save_idea(conn, idea_dict)
                idea_dict["id"] = idea_id
                idea_records.append(idea_dict)

            # ----- CHALLENGER -----
            survivors: list[tuple[dict, dict]] = []
            for idea_dict in idea_records:
                with agent_status("challenger"):
                    ch_out = run_with_reflexion(
                        agent=challenger,
                        context={"idea": idea_dict},
                        reflection_prompt_fn=lambda ctx, out: challenger_reflection_prompt(
                            idea=ctx["idea"], challenger_output=out,
                        ),
                    )
                ch_dict = ch_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "challenger", ch_dict)

                if ch_dict["verdict"] == "SURVIVE":
                    survivors.append((idea_dict, ch_dict))
                    display_challenger_result(idea_dict["name"], survived=True)
                else:
                    repo.update_idea_status(conn, idea_dict["id"], "killed")
                    recent_rejections.append(idea_dict["name"])
                    display_challenger_result(idea_dict["name"], survived=False)

            if not survivors:
                console.print(
                    "\n  [yellow]No survivors this round. Generating new batch...[/yellow]\n"
                )
                time.sleep(PACE_BETWEEN_LOOPS)
                continue

            top_survivors = survivors[:TOP_K]
            console.print(
                f"\n  [bold bright_cyan]{len(top_survivors)} idea(s) advancing to full evaluation[/bold bright_cyan]\n"
            )

            # ----- FULL PIPELINE for each survivor -----
            finalists: list[tuple[dict, dict]] = []
            for idea_dict, ch_dict in top_survivors:
                console.rule(
                    f"[bold bright_white]{idea_dict['name']}[/bold bright_white]",
                    style="dim",
                )

                # Builder
                with agent_status("builder"):
                    b_out = builder.run({"idea": idea_dict})
                b_dict = b_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "builder", b_dict)

                if not b_dict.get("buildable", True):
                    console.print("  [bold red]NOT BUILDABLE[/bold red] [dim]— skipping[/dim]")
                    repo.update_idea_status(conn, idea_dict["id"], "unbuildable")
                    continue

                # Distributor
                with agent_status("distributor"):
                    d_out = distributor.run({
                        "idea": idea_dict,
                        "build_output": b_dict,
                    })
                d_dict = d_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "distributor", d_dict)

                # Consumer
                with agent_status("consumer"):
                    c_out = consumer.run({
                        "idea": idea_dict,
                        "build_output": b_dict,
                        "dist_output": d_dict,
                    })
                c_dict = c_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "consumer", c_dict)

                # Judge
                with agent_status("judge"):
                    j_out = run_with_reflexion(
                        agent=judge,
                        context={
                            "idea": idea_dict,
                            "challenger_out": ch_dict,
                            "builder_out": b_dict,
                            "dist_out": d_dict,
                            "consumer_out": c_dict,
                        },
                        reflection_prompt_fn=lambda ctx, out: judge_reflection_prompt(
                            idea=ctx["idea"], judge_output=out,
                        ),
                    )
                j_dict = j_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "judge", j_dict)

                # Update idea status
                verdict = j_dict.get("verdict", "PASS").upper()
                repo.update_idea_status(
                    conn, idea_dict["id"], verdict.lower(), j_dict.get("composite_score")
                )

                finalists.append((idea_dict, j_dict))
                display_idea_card(idea_dict, j_dict)

                # Claude Check (optional)
                if claude_check_agent:
                    with agent_status("claude_check"):
                        cc_out = claude_check_agent.run({
                            "idea": idea_dict,
                            "judge_output": j_dict,
                            "builder_output": b_dict,
                        })
                    cc_dict = cc_out.model_dump()
                    repo.save_agent_output(conn, idea_dict["id"], "claude_check", cc_dict)
                    display_claude_check(idea_dict, cc_dict)

                time.sleep(PACE_BETWEEN_IDEAS)

            display_loop_summary(
                loop_num,
                len(idea_records),
                len(survivors),
                len(finalists),
            )

            # ----- TASTE AGENT (replaces human feedback) -----
            if finalists:
                for idea_dict, j_dict in finalists:
                    with agent_status("taste"):
                        taste_out = taste.run({
                            "idea": idea_dict,
                            "judge_output": j_dict,
                            "persona_description": persona_description,
                        })
                    fb_dict = taste_out.model_dump()
                    repo.save_feedback(conn, idea_dict["id"], fb_dict)

                    # Update preferences from AI feedback
                    prefs = update_preferences(prefs, fb_dict, idea_dict, j_dict)
                    save_preferences(conn, prefs)

                    display_taste_feedback(idea_dict, fb_dict, persona_label)

                    # Update scoreboard
                    _update_scoreboard(
                        scoreboard,
                        idea_dict,
                        j_dict,
                        fb_dict,
                    )

                    time.sleep(PACE_BETWEEN_IDEAS)

            # ----- SCOREBOARD -----
            if scoreboard:
                display_scoreboard(scoreboard)

            # Pace before next loop
            console.print(
                f"  [dim]Next loop in {PACE_BETWEEN_LOOPS}s... (Ctrl+C to stop)[/dim]\n"
            )
            time.sleep(PACE_BETWEEN_LOOPS)

    except GracefulExit:
        console.print()
        save_preferences(conn, prefs)
        console.print(
            Panel(
                f"[bold]Loops completed:[/bold]  {loop_num}\n"
                f"[bold]Ideas scored:[/bold]     {len(scoreboard)}\n\n"
                f"[dim]State saved. Run [bold]idea-factory livestream[/bold] to resume.[/dim]",
                title="[bold yellow]Livestream Ended[/bold yellow]",
                border_style="yellow",
                expand=False,
                padding=(1, 2),
            )
        )
        # Show final scoreboard
        if scoreboard:
            display_scoreboard(scoreboard)
    finally:
        signal.signal(signal.SIGINT, prev_handler)
        conn.close()


def _update_scoreboard(
    scoreboard: list[dict],
    idea: dict,
    judge_output: dict,
    taste_feedback: dict,
) -> None:
    """Insert idea into the in-memory top-10 scoreboard, sorted by composite score."""
    entry = {
        "name": idea.get("name", "?"),
        "composite_score": judge_output.get("composite_score", 0),
        "verdict": judge_output.get("verdict", "PASS"),
        "taste_decision": taste_feedback.get("decision", "?"),
        "taste_rating": taste_feedback.get("rating", 0),
    }
    scoreboard.append(entry)
    # Sort by composite score descending, keep top 10
    scoreboard.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
    while len(scoreboard) > 10:
        scoreboard.pop()

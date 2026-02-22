"""Main continuous loop orchestrator for the idea generation pipeline."""

from __future__ import annotations

import signal

from rich.panel import Panel

from idea_factory.agents.builder import BuilderAgent
from idea_factory.agents.challenger import ChallengerAgent
from idea_factory.agents.claude_check import ClaudeCheckAgent
from idea_factory.agents.consumer import ConsumerAgent
from idea_factory.agents.creator import CreatorAgent
from idea_factory.agents.distributor import DistributorAgent
from idea_factory.agents.judge import JudgeAgent
from idea_factory.config import Settings, build_domain_niches_hint
from idea_factory.db import repository as repo
from idea_factory.db.connection import get_db
from idea_factory.display import (
    agent_status,
    console,
    display_challenger_result,
    display_claude_check,
    display_idea_card,
    display_loop_summary,
    prompt_feedback,
)
from idea_factory.llm.base import LLMProvider
from idea_factory.llm.factory import get_provider
from idea_factory.models import ConceptFingerprint
from idea_factory.preferences import (
    build_taste_prefix,
    load_preferences,
    save_preferences,
    update_preferences,
)
from idea_factory.prompts import (
    challenger_reflection_prompt,
    concept_fingerprint_prompt,
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


def _generate_concept_fingerprint(
    provider: LLMProvider, idea_dict: dict
) -> ConceptFingerprint | None:
    """Generate a concept fingerprint for an idea. Returns None on failure (non-critical)."""
    try:
        sys_p, usr_p = concept_fingerprint_prompt(idea_dict)
        result: ConceptFingerprint = provider.generate(sys_p, usr_p, ConceptFingerprint)
        return result
    except Exception:
        return None


class GracefulExit(Exception):
    pass


def _handle_sigint(sig: int, frame: object) -> None:
    raise GracefulExit()


def run_loop(
    region: str,
    domains: list[str],
    constraints: str,
    settings: Settings,
    session_id: int = 0,
    claude_check: bool = False,
) -> None:
    """Run the continuous idea generation + evaluation loop."""
    top_k = settings.top_k
    max_winners = settings.max_winners

    conn = get_db(settings.db_path)
    provider = get_provider(settings)

    # Agents
    creator = CreatorAgent(provider)
    challenger = ChallengerAgent(provider)
    builder = BuilderAgent(provider)
    distributor = DistributorAgent(provider)
    consumer = ConsumerAgent(provider)
    judge = JudgeAgent(provider)
    claude_check_agent = ClaudeCheckAgent(provider) if claude_check else None

    # State — restore from session if resuming
    prefs = load_preferences(conn)
    recent_rejections: list[dict] = []
    if session_id:
        session = repo.get_latest_session(conn)
        if session and session["id"] == session_id:
            loop_num = session["loop_num"]
            total_winners = session["total_winners"]
        else:
            loop_num = 0
            total_winners = 0
        recent_rejections = repo.get_recent_rejections(conn, session_id)
    else:
        loop_num = 0
        total_winners = 0

    # Load cross-session rejected concepts and merge in
    cross_session_concepts = repo.get_rejected_concepts(conn, limit=30)
    # Deduplicate by name — session rejections take priority
    seen_names = {r["name"] for r in recent_rejections}
    for c in cross_session_concepts:
        if c["name"] not in seen_names:
            recent_rejections.append(
                {"name": c["name"], "concept_summary": c.get("concept_summary", "")}
            )
            seen_names.add(c["name"])

    # Graceful exit
    prev_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _handle_sigint)

    try:
        while True:
            loop_num += 1
            console.rule(f"[bold]Loop {loop_num}[/bold]")

            # ----- CREATOR -----
            taste_prefix = build_taste_prefix(prefs)
            domain_niches_hint = build_domain_niches_hint(domains)
            with agent_status("creator"):
                creator_out = creator.run(
                    {
                        "region": region,
                        "domains": domains,
                        "constraints": constraints,
                        "taste_prefix": taste_prefix,
                        "recent_rejections": recent_rejections,
                        "domain_niches_hint": domain_niches_hint,
                    }
                )
            ideas = creator_out.ideas  # type: ignore[attr-defined]
            _track_usage(conn, creator, None, settings)
            console.print(f"  [bold green]{len(ideas)} ideas generated[/bold green]\n")

            # Save ideas to DB
            idea_records: list[dict] = []
            for idea in ideas:
                idea_dict = idea.model_dump()
                idea_id = repo.save_idea(conn, idea_dict)
                idea_dict["id"] = idea_id
                idea_records.append(idea_dict)

            # ----- CHALLENGER -----
            survivors: list[tuple[dict, dict]] = []  # (idea, challenger_output)
            for idea_dict in idea_records:
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
                repo.save_agent_output(conn, idea_dict["id"], "challenger", ch_dict)
                _track_usage(conn, challenger, idea_dict["id"], settings)

                if ch_dict["verdict"] == "SURVIVE":
                    survivors.append((idea_dict, ch_dict))
                    display_challenger_result(
                        idea_dict["name"],
                        survived=True,
                        one_liner=idea_dict.get("one_liner", ""),
                    )
                else:
                    repo.update_idea_status(conn, idea_dict["id"], "killed")
                    # Generate concept fingerprint for rejection memory
                    fp = _generate_concept_fingerprint(provider, idea_dict)
                    concept_summary = fp.concept_summary if fp else ""
                    if fp:
                        repo.save_concept(
                            conn,
                            idea_dict["id"],
                            fp.concept_summary,
                            fp.problem_domain,
                            rejection_source="challenger_kill",
                        )
                    recent_rejections.append(
                        {"name": idea_dict["name"], "concept_summary": concept_summary}
                    )
                    display_challenger_result(
                        idea_dict["name"],
                        survived=False,
                        one_liner=idea_dict.get("one_liner", ""),
                    )

            if not survivors:
                console.print(
                    "\n  [yellow]No survivors this round. Generating new batch...[/yellow]\n"
                )
                continue

            # Take top-K survivors (first K by order)
            top_survivors = survivors[:top_k]
            n_adv = len(top_survivors)
            console.print(
                f"\n  [bold bright_cyan]{n_adv} idea(s)"
                " advancing to full evaluation"
                "[/bold bright_cyan]\n"
            )

            # ----- FULL PIPELINE for each survivor -----
            # Fetch historical concepts for Judge novelty comparison
            historical_concepts = repo.get_rejected_concepts(conn, limit=15)
            finalists: list[tuple[dict, dict]] = []  # (idea, judge_dict)
            for idea_dict, ch_dict in top_survivors:
                name = idea_dict["name"]
                console.rule(
                    f"[bold bright_white]{name}[/bold bright_white]",
                    style="dim",
                )

                # Builder
                with agent_status("builder"):
                    b_out = builder.run({"idea": idea_dict})
                b_dict = b_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "builder", b_dict)
                _track_usage(conn, builder, idea_dict["id"], settings)

                if not b_dict.get("buildable", True):
                    console.print("  [bold red]NOT BUILDABLE[/bold red] [dim]— skipping[/dim]")
                    repo.update_idea_status(conn, idea_dict["id"], "unbuildable")
                    continue

                # Distributor
                with agent_status("distributor"):
                    d_out = distributor.run(
                        {
                            "idea": idea_dict,
                            "build_output": b_dict,
                        }
                    )
                d_dict = d_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "distributor", d_dict)
                _track_usage(conn, distributor, idea_dict["id"], settings)

                # Consumer
                with agent_status("consumer"):
                    c_out = consumer.run(
                        {
                            "idea": idea_dict,
                            "build_output": b_dict,
                            "dist_output": d_dict,
                        }
                    )
                c_dict = c_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "consumer", c_dict)
                _track_usage(conn, consumer, idea_dict["id"], settings)

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
                            "historical_concepts": historical_concepts,
                        },
                        reflection_prompt_fn=lambda ctx, out: judge_reflection_prompt(
                            idea=ctx["idea"],
                            judge_output=out,
                        ),
                        max_rounds=settings.reflexion_max_rounds,
                    )
                j_dict = j_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "judge", j_dict)
                _track_usage(conn, judge, idea_dict["id"], settings)

                # Update idea status based on verdict
                verdict = j_dict.get("verdict", "PASS").lower()
                repo.update_idea_status(
                    conn, idea_dict["id"], verdict, j_dict.get("composite_score")
                )

                finalists.append((idea_dict, j_dict))
                display_idea_card(idea_dict, j_dict)

                # Claude Check (optional)
                if claude_check_agent:
                    with agent_status("claude_check"):
                        cc_out = claude_check_agent.run(
                            {
                                "idea": idea_dict,
                                "judge_output": j_dict,
                                "builder_output": b_dict,
                            }
                        )
                    cc_dict = cc_out.model_dump()
                    repo.save_agent_output(conn, idea_dict["id"], "claude_check", cc_dict)
                    _track_usage(conn, claude_check_agent, idea_dict["id"], settings)
                    display_claude_check(idea_dict, cc_dict)

            display_loop_summary(
                loop_num,
                len(idea_records),
                len(survivors),
                len(finalists),
            )

            # ----- USER FEEDBACK -----
            if not finalists:
                console.print("  [yellow]No finalists this round.[/yellow]\n")
                if session_id:
                    repo.update_session_progress(conn, session_id, loop_num, total_winners)
                continue

            for idea_dict, j_dict in finalists:
                fb = prompt_feedback(idea_dict)
                repo.save_feedback(conn, idea_dict["id"], fb)
                prefs = update_preferences(prefs, fb, idea_dict, j_dict)
                save_preferences(conn, prefs)

                # Store concept fingerprint for hate/meh feedback
                if fb["decision"] in ("hate", "meh"):
                    fp = _generate_concept_fingerprint(provider, idea_dict)
                    if fp:
                        repo.save_concept(
                            conn,
                            idea_dict["id"],
                            fp.concept_summary,
                            fp.problem_domain,
                            rejection_source=f"user_{fb['decision']}",
                        )
                        recent_rejections.append(
                            {"name": idea_dict["name"], "concept_summary": fp.concept_summary}
                        )

                if fb["decision"] == "love" and j_dict.get("verdict") == "WINNER":
                    total_winners += 1
                    console.print(
                        f"[bold green]★ WINNER #{total_winners}: {idea_dict['name']}[/bold green]"
                    )

            # Persist session progress
            if session_id:
                repo.update_session_progress(conn, session_id, loop_num, total_winners)

            if total_winners >= max_winners:
                console.print(
                    f"\n[bold green]Reached {max_winners} winners! Wrapping up.[/bold green]"
                )
                break

            console.print()

    except GracefulExit:
        console.print()
        save_preferences(conn, prefs)
        if session_id:
            repo.update_session_progress(conn, session_id, loop_num, total_winners)
        console.print(
            Panel(
                f"[bold]Loops completed:[/bold]  {loop_num}\n"
                f"[bold]Winners found:[/bold]    {total_winners}\n\n"
                f"[dim]State saved. Run [bold]idea-factory start[/bold] to continue.[/dim]",
                title="[bold yellow]Session Ended[/bold yellow]",
                border_style="yellow",
                expand=False,
                padding=(1, 2),
            )
        )
    finally:
        signal.signal(signal.SIGINT, prev_handler)
        conn.close()

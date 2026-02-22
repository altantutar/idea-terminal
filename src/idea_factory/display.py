"""Rich-based terminal rendering helpers."""

from __future__ import annotations

import json
from typing import Any

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

console = Console()

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------

LOGO = r"""
  [bold bright_cyan] ___ ____  _____    _      [/bold bright_cyan]
  [bold bright_cyan]|_ _|  _ \| ____|  / \     [/bold bright_cyan]
  [bold bright_cyan] | || | | |  _|   / _ \    [/bold bright_cyan]
  [bold bright_cyan] | || |_| | |___ / ___ \   [/bold bright_cyan]
  [bold bright_cyan]|___|____/|_____/_/   \_\  [/bold bright_cyan]
  [bold white]F  A  C  T  O  R  Y[/bold white]
"""


def display_banner() -> None:
    """Show the branded welcome banner."""
    console.print(
        Panel(
            LOGO,
            subtitle="[dim]6-agent startup idea evaluator[/dim]",
            border_style="bright_cyan",
            expand=False,
            padding=(0, 2),
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# Provider detection display
# ---------------------------------------------------------------------------

def display_session_resume(session: dict) -> None:
    """Show a panel summarizing the previous session for resume prompt."""
    domains = session.get("domains", [])
    if isinstance(domains, str):
        domains = json.loads(domains)
    domain_str = ", ".join(domains) if domains else "—"
    constraints = session.get("constraints", "") or "none"
    console.print(
        Panel(
            f"[bold]Region:[/bold]       {session.get('region', '?')}\n"
            f"[bold]Domains:[/bold]      {domain_str}\n"
            f"[bold]Constraints:[/bold]  {constraints}\n"
            f"[bold]Loops done:[/bold]   {session.get('loop_num', 0)}\n"
            f"[bold]Winners:[/bold]      {session.get('total_winners', 0)}\n"
            f"[dim]Last active:  {session.get('updated_at', '?')}[/dim]",
            title="[bold bright_cyan]Previous Session[/bold bright_cyan]",
            border_style="bright_cyan",
            expand=False,
            padding=(1, 2),
        )
    )
    console.print()


def display_provider_detected(provider: str, model: str) -> None:
    key_label = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    console.print(
        Panel(
            f"[green]Detected {key_label}[/green]\n"
            f"[dim]Provider:[/dim] [bold]{provider}[/bold]  "
            f"[dim]Model:[/dim] [bold]{model}[/bold]",
            border_style="green",
            expand=False,
            padding=(0, 2),
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# Domain picker
# ---------------------------------------------------------------------------

def display_domain_picker() -> None:
    """Render the domain list as a two-column numbered grid."""
    from idea_factory.cli import DOMAIN_CHOICES

    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
        expand=False,
    )
    table.add_column(width=38)
    table.add_column(width=38)

    mid = (len(DOMAIN_CHOICES) + 1) // 2
    for i in range(mid):
        left = f"[bold bright_cyan]{i + 1:>2}.[/bold bright_cyan]  {DOMAIN_CHOICES[i]}"
        right_idx = i + mid
        if right_idx < len(DOMAIN_CHOICES):
            right = (
                f"[bold bright_cyan]{right_idx + 1:>2}."
                f"[/bold bright_cyan]  {DOMAIN_CHOICES[right_idx]}"
            )
        else:
            right = ""
        table.add_row(left, right)

    console.print(
        Panel(
            table,
            title="[bold]Select Domains[/bold]",
            border_style="bright_blue",
            expand=False,
            padding=(1, 2),
        )
    )


# ---------------------------------------------------------------------------
# Idea card
# ---------------------------------------------------------------------------

_VERDICT_STYLE = {
    "WINNER": ("bold green", "WINNER"),
    "CONTENDER": ("bold yellow", "CONTENDER"),
    "PASS": ("bold red", "PASS"),
}

_SCORE_BLOCK = "█"
_SCORE_EMPTY = "░"


def _score_bar(value: int, max_val: int = 10, width: int = 10) -> str:
    """Render a tiny inline bar: ████░░░░░░ 7/10"""
    filled = min(value, max_val)
    if filled >= 8:
        color = "green"
    elif filled >= 5:
        color = "yellow"
    else:
        color = "red"
    bar = (
        f"[{color}]{_SCORE_BLOCK * filled}[/{color}]"
        f"[dim]{_SCORE_EMPTY * (max_val - filled)}[/dim]"
    )
    return f"{bar} [bold]{value}[/bold]/{max_val}"


def display_idea_card(idea: dict, judge_output: dict | None = None) -> None:
    """Render a single idea as a polished Rich Panel."""
    tags = idea.get("tags", [])
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            tags = []

    # Header
    lines = [
        f"[bold bright_white]{idea['name']}[/bold bright_white]",
        f"[italic bright_cyan]{idea.get('one_liner', '')}[/italic bright_cyan]",
    ]

    # Tag pills
    if tags:
        tag_str = "  ".join(f"[on grey23] {t} [/on grey23]" for t in tags)
        lines.append(tag_str)

    lines.append("")

    # Details grid
    detail_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    detail_table.add_column("label", style="bold", width=14, no_wrap=True)
    detail_table.add_column("value")
    detail_table.add_row("Domain", idea.get("domain", ""))
    detail_table.add_row("Target user", idea.get("target_user", ""))
    detail_table.add_row("Monetization", idea.get("monetization", ""))
    detail_table.add_row("Region", idea.get("region", ""))

    # Scores section
    score_table = None
    verdict_line = None
    if judge_output:
        scores = judge_output.get("scores", {})
        score_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        score_table.add_column("metric", style="bold", width=18, no_wrap=True)
        score_table.add_column("bar")
        for label, val in scores.items():
            nice_label = label.replace("_", " ").title()
            score_table.add_row(nice_label, _score_bar(val))

        composite = judge_output.get("composite_score", 0)
        verdict = judge_output.get("verdict", "PASS")
        style, label = _VERDICT_STYLE.get(verdict, ("white", verdict))
        verdict_line = (
            f"[bold]Composite:[/bold] [bold bright_white]{composite:.1f}[/bold bright_white]/10"
            f"    [{style}]{label}[/{style}]"
        )
        if judge_output.get("one_line_summary"):
            verdict_line += f"\n[dim italic]{judge_output['one_line_summary']}[/dim italic]"

    # Assemble
    parts: list[Any] = ["\n".join(lines), "", detail_table]

    # Problem / Solution
    parts.append("")
    parts.append(f"[bold]Problem:[/bold]  {idea.get('problem', '')}")
    parts.append(f"[bold]Solution:[/bold] {idea.get('solution', '')}")

    if score_table:
        parts.append("")
        parts.append(Text("─" * 50, style="dim"))
        parts.append(score_table)
    if verdict_line:
        parts.append("")
        parts.append(verdict_line)

    # Pick border color based on verdict
    if judge_output:
        verdict = judge_output.get("verdict", "PASS")
        border = {
            "WINNER": "green", "CONTENDER": "yellow", "PASS": "red",
        }.get(verdict, "bright_blue")
    else:
        border = "bright_blue"

    body = Group(*[p if not isinstance(p, str) else Text.from_markup(p) for p in parts])
    panel = Panel(
        body,
        title=f"[bold] Idea #{idea.get('id', '?')} [/bold]",
        title_align="left",
        border_style=border,
        expand=False,
        width=76,
        padding=(1, 2),
    )
    console.print(panel)
    console.print()


# ---------------------------------------------------------------------------
# Agent progress
# ---------------------------------------------------------------------------

_AGENT_DESCRIPTIONS = {
    "creator": "Generating ideas",
    "challenger": "Stress-testing idea",
    "builder": "Assessing feasibility",
    "distributor": "Designing go-to-market",
    "consumer": "Simulating user reactions",
    "judge": "Scoring and judging",
    "taste": "AI persona reacting",
    "claude_check": "Can Claude one-shot this?",
}


def agent_status(agent_name: str):
    """Return a Rich status context manager for an agent call."""
    desc = _AGENT_DESCRIPTIONS.get(agent_name, "Thinking")
    return console.status(
        f"  [bold bright_cyan]{agent_name.upper()}[/bold bright_cyan] [dim]{desc}...[/dim]",
        spinner="dots",
    )


# ---------------------------------------------------------------------------
# Challenger results
# ---------------------------------------------------------------------------

def display_challenger_result(name: str, survived: bool, one_liner: str = "") -> None:
    liner = f"\n                {one_liner}" if one_liner else ""
    if survived:
        console.print(f"  [bold green]SURVIVE[/bold green]  {name}[dim]{liner}[/dim]")
    else:
        console.print(f"  [bold red]  KILL [/bold red]  [dim]{name}{liner}[/dim]")


# ---------------------------------------------------------------------------
# Loop summary
# ---------------------------------------------------------------------------

def display_loop_summary(
    loop_num: int,
    ideas_generated: int,
    survivors: int,
    finalists: int,
) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    table.add_column("metric", style="dim")
    table.add_column("value", style="bold", justify="right")
    table.add_row("Generated", str(ideas_generated))
    table.add_row("Survived", f"[green]{survivors}[/green]")
    table.add_row("Evaluated", f"[bright_cyan]{finalists}[/bright_cyan]")
    console.print(
        Panel(
            table,
            title=f"[bold]Loop {loop_num} Summary[/bold]",
            border_style="dim",
            expand=False,
            padding=(0, 2),
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def display_stats(stats: dict[str, Any]) -> None:
    table = Table(box=box.SIMPLE_HEAVY, expand=False, padding=(0, 2))
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    total = stats.get('total_ideas', 0)
    table.add_row(
        "Total ideas",
        f"[bold bright_white]{total}[/bold bright_white]",
    )

    for status, count in stats.get("by_status", {}).items():
        color = {
            "winner": "green", "contender": "yellow",
            "pass": "red", "killed": "red",
        }.get(status, "white")
        table.add_row(f"  {status}", f"[{color}]{count}[/{color}]")

    avg = stats.get("avg_composite_score")
    avg_str = f"{avg:.1f}" if avg else "-"
    table.add_row("Avg score", avg_str)
    table.add_row("Feedback given", str(stats.get("total_feedback", 0)))

    console.print(
        Panel(
            table,
            title="[bold]Idea Factory Stats[/bold]",
            border_style="bright_cyan",
            expand=False,
        )
    )


# ---------------------------------------------------------------------------
# Ideas list
# ---------------------------------------------------------------------------

_STATUS_BADGE = {
    "winner": "[bold green] WINNER [/bold green]",
    "contender": "[bold yellow] CONTENDER [/bold yellow]",
    "pass": "[red] PASS [/red]",
    "killed": "[red dim] KILLED [/red dim]",
    "unbuildable": "[red dim] UNBUILDABLE [/red dim]",
    "pending": "[dim] PENDING [/dim]",
}


def display_ideas_table(ideas: list[dict]) -> None:
    table = Table(box=box.ROUNDED, expand=False, padding=(0, 1))
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Name", style="bold bright_white", max_width=30)
    table.add_column("Domain", style="dim", max_width=22)
    table.add_column("Status", justify="center", width=14)
    table.add_column("Score", justify="right", width=6)

    for idea in ideas:
        score = f"{idea['composite_score']:.1f}" if idea.get("composite_score") else "-"
        status = idea.get("status", "pending")
        badge = _STATUS_BADGE.get(status, status)
        table.add_row(
            str(idea["id"]),
            idea["name"],
            idea.get("domain", ""),
            badge,
            score,
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Full idea detail — formatted agent outputs
# ---------------------------------------------------------------------------

def _format_agent_output(agent_name: str, output: dict) -> Panel:
    """Format a single agent's output as a readable panel."""
    lines: list[str] = []

    if agent_name == "challenger":
        verdict = output.get("verdict", "")
        color = "green" if verdict == "SURVIVE" else "red"
        lines.append(f"[bold]Verdict:[/bold] [{color}]{verdict}[/{color}]")
        if output.get("fatal_flaws"):
            lines.append("\n[bold]Fatal flaws:[/bold]")
            for f in output["fatal_flaws"]:
                lines.append(f"  [red]- {f}[/red]")
        if output.get("risks"):
            lines.append("\n[bold]Risks:[/bold]")
            for r in output["risks"]:
                lines.append(f"  [yellow]- {r}[/yellow]")
        if output.get("competitor_overlap"):
            lines.append(f"\n[bold]Competitors:[/bold] {output['competitor_overlap']}")
        if output.get("survival_reason"):
            lines.append(f"\n[bold]Survival reason:[/bold] {output['survival_reason']}")

    elif agent_name == "builder":
        buildable = output.get("buildable", False)
        build_badge = (
            "[green]Yes[/green]" if buildable else "[red]No[/red]"
        )
        lines.append(f"[bold]Buildable:[/bold] {build_badge}")
        if output.get("mvp_scope"):
            lines.append(f"[bold]MVP scope:[/bold] {output['mvp_scope']}")
        if output.get("tech_stack"):
            lines.append("\n[bold]Tech stack:[/bold]")
            for item in output["tech_stack"]:
                layer = item.get("layer", "") if isinstance(item, dict) else str(item)
                choice = item.get("choice", "") if isinstance(item, dict) else ""
                lines.append(f"  [dim]{layer}:[/dim] {choice}")
        if output.get("milestones"):
            lines.append("\n[bold]Milestones:[/bold]")
            for m in output["milestones"]:
                week = m.get("week", "") if isinstance(m, dict) else str(m)
                goal = m.get("goal", "") if isinstance(m, dict) else ""
                lines.append(f"  [dim]{week}:[/dim] {goal}")
        if output.get("build_risk"):
            lines.append(f"\n[bold]Risk:[/bold] [yellow]{output['build_risk']}[/yellow]")

    elif agent_name == "distributor":
        if output.get("primary_channel"):
            lines.append(f"[bold]Primary channel:[/bold] {output['primary_channel']}")
        if output.get("channels"):
            lines.append("\n[bold]Channels:[/bold]")
            for ch in output["channels"]:
                name = ch.get("channel", "") if isinstance(ch, dict) else str(ch)
                tactic = ch.get("tactic", "") if isinstance(ch, dict) else ""
                cac = ch.get("expected_cac", "") if isinstance(ch, dict) else ""
                line = f"  [bold]{name}[/bold] — {tactic}"
                if cac:
                    line += f" [dim](CAC: {cac})[/dim]"
                lines.append(line)
        if output.get("viral_hook"):
            lines.append(f"\n[bold]Viral hook:[/bold] {output['viral_hook']}")
        if output.get("launch_strategy"):
            lines.append(f"[bold]Launch:[/bold] {output['launch_strategy']}")
        if output.get("moat"):
            lines.append(f"[bold]Moat:[/bold] {output['moat']}")

    elif agent_name == "consumer":
        if output.get("personas"):
            for p in output["personas"]:
                persona = p.get("persona", "") if isinstance(p, dict) else str(p)
                reaction = p.get("reaction", "") if isinstance(p, dict) else ""
                would_pay = p.get("would_pay", False) if isinstance(p, dict) else False
                objection = p.get("objection", "") if isinstance(p, dict) else ""
                pay_badge = "[green]would pay[/green]" if would_pay else "[red]won't pay[/red]"
                lines.append(f"[bold]{persona}[/bold] ({pay_badge})")
                lines.append(f"  {reaction}")
                if objection:
                    lines.append(f"  [dim italic]Objection: {objection}[/dim italic]")
                lines.append("")
        excitement = output.get("overall_excitement", "?")
        wtp = output.get("willingness_to_pay", "?")
        exc_display = (
            _score_bar(excitement) if isinstance(excitement, int)
            else excitement
        )
        wtp_display = (
            _score_bar(wtp) if isinstance(wtp, int) else wtp
        )
        lines.append(f"[bold]Excitement:[/bold] {exc_display}")
        lines.append(f"[bold]WTP:[/bold]        {wtp_display}")
        if output.get("key_objection"):
            lines.append(f"\n[bold]Key objection:[/bold] {output['key_objection']}")

    elif agent_name == "judge":
        scores = output.get("scores", {})
        for label, val in scores.items():
            nice = label.replace("_", " ").title()
            lines.append(f"  {nice:18s} {_score_bar(val) if isinstance(val, int) else val}")
        composite = output.get("composite_score", 0)
        lines.append(f"\n[bold]Composite:[/bold] {composite:.1f}/10")
        verdict = output.get("verdict", "")
        style = {
            "WINNER": "bold green",
            "CONTENDER": "bold yellow",
            "PASS": "bold red",
        }.get(verdict, "white")
        lines.append(f"[bold]Verdict:[/bold] [{style}]{verdict}[/{style}]")
        if output.get("one_line_summary"):
            lines.append(f"[dim italic]{output['one_line_summary']}[/dim italic]")
        if output.get("archetype"):
            lines.append(f"[bold]Archetype:[/bold] {output['archetype']}")

    elif agent_name == "claude_check":
        verdict = output.get("verdict", "")
        v_style = {
            "one_shottable": "bold red",
            "needs_work": "bold yellow",
            "not_feasible": "bold green",
        }.get(verdict, "white")
        lines.append(f"[bold]Verdict:[/bold] [{v_style}]{verdict}[/{v_style}]")
        if output.get("claude_product"):
            lines.append(f"[bold]Claude product:[/bold] {output['claude_product']}")
        if output.get("time_estimate"):
            lines.append(f"[bold]Time estimate:[/bold] {output['time_estimate']}")
        if output.get("what_it_builds"):
            lines.append(f"\n[bold]What Claude builds:[/bold] {output['what_it_builds']}")
        if output.get("what_it_cant"):
            lines.append(f"[bold]What it can't:[/bold] {output['what_it_cant']}")
        if output.get("defensibility_note"):
            defense = output['defensibility_note']
            lines.append(
                f"\n[bold]Defensibility:[/bold]"
                f" [italic]{defense}[/italic]"
            )

    else:
        # Fallback: pretty-print JSON
        lines.append(json.dumps(output, indent=2))

    agent_colors = {
        "challenger": "red",
        "builder": "bright_cyan",
        "distributor": "magenta",
        "consumer": "bright_yellow",
        "judge": "bright_green",
        "claude_check": "cyan",
    }
    border = agent_colors.get(agent_name, "dim")

    return Panel(
        "\n".join(lines),
        title=f"[bold] {agent_name.upper()} [/bold]",
        title_align="left",
        border_style=border,
        expand=False,
        width=76,
        padding=(1, 2),
    )


def display_idea_detail(idea: dict, agent_outputs: list[dict]) -> None:
    display_idea_card(idea)
    for ao in agent_outputs:
        agent = ao.get("agent_name", "unknown")
        output = ao.get("output", ao.get("output_json", {}))
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                pass
        if isinstance(output, dict):
            console.print(_format_agent_output(agent, output))
        else:
            console.print(
                Panel(
                    str(output),
                    title=f"Agent: {agent.upper()}",
                    border_style="dim",
                    expand=False,
                    width=76,
                )
            )


# ---------------------------------------------------------------------------
# Preferences display
# ---------------------------------------------------------------------------

def display_preferences(prefs: Any) -> None:
    """Show current preference weights."""
    from idea_factory.preferences import PreferenceState

    if isinstance(prefs, PreferenceState):
        data = {
            "Domain weights": prefs.domain_weights,
            "Rejected tag weights": prefs.reject_tag_weights,
            "Channel weights": prefs.channel_weights,
            "Hard nos": prefs.hard_nos,
            "Archetype weights": prefs.archetype_weights,
        }
    else:
        data = prefs

    if not any(data.values()):
        console.print(
            Panel(
                "[dim]No preferences learned yet."
                " Run some loops to teach the system"
                " your taste![/dim]",
                border_style="dim",
                expand=False,
            )
        )
        return

    lines: list[str] = []
    for key, value in data.items():
        if not value:
            continue
        lines.append(f"\n[bold bright_cyan]{key}[/bold bright_cyan]")
        if isinstance(value, dict):
            for k, v in sorted(value.items(), key=lambda x: -abs(x[1])):
                color = "green" if v > 0 else "red"
                bar_val = int(min(abs(v), 10))
                bar = f"[{color}]{_SCORE_BLOCK * bar_val}[/{color}]"
                lines.append(f"  {k:24s} {bar} [{color}]{v:+.1f}[/{color}]")
        elif isinstance(value, list):
            for item in value:
                lines.append(f"  [red]- {item}[/red]")

    console.print(
        Panel(
            "\n".join(lines),
            title="[bold]Learned Preferences[/bold]",
            border_style="bright_cyan",
            expand=False,
            width=76,
            padding=(1, 2),
        )
    )


# ---------------------------------------------------------------------------
# User feedback prompt
# ---------------------------------------------------------------------------

_DECISION_DISPLAY = {
    "love": "[bold green]love[/bold green]",
    "like": "[green]like[/green]",
    "meh": "[yellow]meh[/yellow]",
    "hate": "[red]hate[/red]",
}


def prompt_feedback(idea: dict) -> dict:
    """Interactively collect user feedback on an idea."""
    console.print()
    console.print(
        Panel(
            f"[bold bright_white]{idea['name']}[/bold bright_white]\n"
            f"[dim]{idea.get('one_liner', '')}[/dim]",
            title="[bold]Your Feedback[/bold]",
            border_style="bright_magenta",
            expand=False,
            width=76,
            padding=(1, 2),
        )
    )
    console.print(
        "  [dim]love[/dim] = build this now  "
        "[dim]like[/dim] = promising  "
        "[dim]meh[/dim] = not excited  "
        "[dim]hate[/dim] = never again"
    )
    decision = Prompt.ask(
        "  Verdict",
        choices=["love", "like", "meh", "hate"],
        default="like",
    )
    rating = IntPrompt.ask("  Rating (1-10)", default=5)
    rating = max(1, min(10, rating))

    tags_raw = Prompt.ask(
        "  Tags to remember (comma-separated, or skip)",
        default="",
    )
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    note = Prompt.ask("  Notes (or skip)", default="")

    console.print(
        f"  [dim]Recorded:[/dim] {_DECISION_DISPLAY.get(decision, decision)} "
        f"[dim]|[/dim] {_score_bar(rating)}"
    )
    console.print()

    return {
        "decision": decision,
        "rating": rating,
        "tags": tags,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Livestream mode display helpers
# ---------------------------------------------------------------------------

LIVESTREAM_LOGO = r"""
  [bold red] ___ ____  _____    _      [/bold red]
  [bold red]|_ _|  _ \| ____|  / \     [/bold red]
  [bold red] | || | | |  _|   / _ \    [/bold red]
  [bold red] | || |_| | |___ / ___ \   [/bold red]
  [bold red]|___|____/|_____/_/   \_\  [/bold red]
  [bold white]F  A  C  T  O  R  Y[/bold white]
  [bold red on white]  LIVESTREAM  [/bold red on white]
"""


def display_livestream_banner(persona_label: str) -> None:
    """Show the branded livestream banner with persona info."""
    console.print(
        Panel(
            LIVESTREAM_LOGO
            + f"\n  [dim]Persona:[/dim]"
            f" [bold magenta]{persona_label}[/bold magenta]",
            subtitle="[dim]autonomous agent mode[/dim]",
            border_style="red",
            expand=False,
            padding=(0, 2),
        )
    )
    console.print()


def display_persona_picker() -> None:
    """Render the persona picker as a numbered list."""
    from idea_factory.personas import FAMOUS_NAMES, TYPE_NAMES

    table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    table.add_column(width=50)

    # Famous personas
    for i, name in enumerate(FAMOUS_NAMES, 1):
        table.add_row(
            f"[bold bright_cyan]{i:>2}.[/bold bright_cyan]  [bold]{name.title()}[/bold]"
        )

    # Separator
    table.add_row("[dim]--- Archetypes ---[/dim]")

    # Archetype personas
    offset = len(FAMOUS_NAMES)
    for i, name in enumerate(TYPE_NAMES, offset + 1):
        table.add_row(
            f"[bold bright_cyan]{i:>2}.[/bold bright_cyan]  [bold]{name.title()}[/bold]"
        )

    table.add_row("")
    table.add_row("[dim]Or type: a name, @handle, or custom description[/dim]")

    console.print(
        Panel(
            table,
            title="[bold]Choose a Persona[/bold]",
            border_style="magenta",
            expand=False,
            padding=(1, 2),
        )
    )


def display_taste_feedback(
    idea: dict, feedback: dict, persona_label: str
) -> None:
    """Show the Taste Agent's reaction in a magenta panel."""
    decision = feedback.get("decision", "?")
    rating = feedback.get("rating", 0)
    note = feedback.get("note", "")
    tags = feedback.get("tags", [])

    decision_display = _DECISION_DISPLAY.get(decision, decision)
    tag_str = ", ".join(tags) if tags else ""

    lines = [
        f"[bold bright_white]{idea.get('name', '?')}[/bold bright_white]",
        f"[dim italic]{idea.get('one_liner', '')}[/dim italic]",
        "",
        f"[bold]{persona_label}[/bold] says: {decision_display}  |  {_score_bar(rating)}",
    ]
    if note:
        lines.append(f'[italic]"{note}"[/italic]')
    if tag_str:
        lines.append(f"[dim]Tags: {tag_str}[/dim]")

    console.print(
        Panel(
            "\n".join(lines),
            title="[bold] TASTE AGENT [/bold]",
            title_align="left",
            border_style="magenta",
            expand=False,
            width=76,
            padding=(1, 2),
        )
    )
    console.print()


def display_claude_check(idea: dict, claude_check_output: dict) -> None:
    """Show the Claude Check agent's verdict in a cyan panel."""
    verdict = claude_check_output.get("verdict", "?")
    product = claude_check_output.get("claude_product", "?")
    time_est = claude_check_output.get("time_estimate", "?")
    builds = claude_check_output.get("what_it_builds", "")
    cant = claude_check_output.get("what_it_cant", "")
    defense = claude_check_output.get("defensibility_note", "")

    verdict_style = {
        "one_shottable": "bold red",
        "needs_work": "bold yellow",
        "not_feasible": "bold green",
    }.get(verdict, "white")

    lines = [
        f"[bold bright_white]{idea.get('name', '?')}[/bold bright_white]",
        f"[dim italic]{idea.get('one_liner', '')}[/dim italic]",
        "",
        f"[bold]Verdict:[/bold]  [{verdict_style}]"
        f"{verdict.upper().replace('_', ' ')}[/{verdict_style}]",
        f"[bold]Product:[/bold]  {product}",
        f"[bold]Time:[/bold]     {time_est}",
    ]
    if builds:
        lines.append(f"\n[bold]What Claude builds:[/bold]\n  [white]{builds}[/white]")
    if cant:
        lines.append(f"\n[bold]What it can't:[/bold]\n  [bright_cyan]{cant}[/bright_cyan]")
    if defense:
        lines.append(f"\n[bold]Defensibility:[/bold]\n  [italic]{defense}[/italic]")

    console.print(
        Panel(
            "\n".join(lines),
            title="[bold] CLAUDE CHECK [/bold]",
            title_align="left",
            border_style="cyan",
            expand=False,
            width=76,
            padding=(1, 2),
        )
    )
    console.print()


def display_costs(summary: dict[str, Any]) -> None:
    """Show API token usage breakdown."""
    total_in = summary.get("total_input_tokens", 0)
    total_out = summary.get("total_output_tokens", 0)
    total = total_in + total_out

    if total == 0:
        console.print(
            Panel(
                "[dim]No token usage recorded yet. Run some loops first![/dim]",
                border_style="dim",
                expand=False,
            )
        )
        return

    # Summary
    summary_table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    summary_table.add_column("label", style="bold")
    summary_table.add_column("value", justify="right")
    summary_table.add_row("Input tokens", f"[bright_cyan]{total_in:,}[/bright_cyan]")
    summary_table.add_row("Output tokens", f"[bright_cyan]{total_out:,}[/bright_cyan]")
    summary_table.add_row("Total tokens", f"[bold bright_white]{total:,}[/bold bright_white]")

    # By agent
    agent_table = Table(box=box.SIMPLE_HEAVY, expand=False, padding=(0, 1))
    agent_table.add_column("Agent", style="bold")
    agent_table.add_column("Calls", justify="right")
    agent_table.add_column("Input", justify="right")
    agent_table.add_column("Output", justify="right")
    agent_table.add_column("Total", justify="right", style="bold")

    for row in summary.get("by_agent", []):
        agent_table.add_row(
            row["agent_name"],
            str(row["calls"]),
            f"{row['input_tokens']:,}",
            f"{row['output_tokens']:,}",
            f"{row['input_tokens'] + row['output_tokens']:,}",
        )

    # By model
    model_lines: list[str] = []
    for row in summary.get("by_model", []):
        model_lines.append(
            f"  [bold]{row['provider']}[/bold] / [dim]{row['model']}[/dim]  "
            f"— {row['calls']} calls, "
            f"[bright_cyan]{row['input_tokens'] + row['output_tokens']:,}[/bright_cyan] tokens"
        )

    parts: list[Any] = [summary_table, "", agent_table]
    if model_lines:
        parts.append("")
        parts.append(Text.from_markup("[bold]By model:[/bold]"))
        for line in model_lines:
            parts.append(Text.from_markup(line))

    body = Group(*[p if not isinstance(p, str) else Text.from_markup(p) for p in parts])
    console.print(
        Panel(
            body,
            title="[bold]API Token Usage[/bold]",
            border_style="bright_cyan",
            expand=False,
            width=76,
            padding=(1, 2),
        )
    )


def display_scoreboard(scoreboard: list[dict]) -> None:
    """Show the top-10 scoreboard as a yellow-bordered table."""
    if not scoreboard:
        return

    table = Table(
        box=box.ROUNDED,
        expand=False,
        padding=(0, 1),
        title="[bold bright_yellow]TOP 10 SCOREBOARD[/bold bright_yellow]",
    )
    table.add_column("#", style="bold bright_yellow", width=4, justify="right")
    table.add_column("Name", style="bold bright_white", max_width=28)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Verdict", justify="center", width=12)
    table.add_column("Taste", justify="center", width=8)

    for rank, entry in enumerate(scoreboard[:10], 1):
        score = f"{entry.get('composite_score', 0):.1f}"
        verdict = entry.get("verdict", "?")
        v_style = {"WINNER": "bold green", "CONTENDER": "bold yellow", "PASS": "red"}.get(
            verdict, "white"
        )
        taste = entry.get("taste_decision", "?")
        t_style = {"love": "bold green", "like": "green", "meh": "yellow", "hate": "red"}.get(
            taste, "white"
        )
        table.add_row(
            str(rank),
            entry.get("name", "?"),
            score,
            f"[{v_style}]{verdict}[/{v_style}]",
            f"[{t_style}]{taste}[/{t_style}]",
        )

    console.print(
        Panel(
            table,
            border_style="bright_yellow",
            expand=False,
            padding=(1, 2),
        )
    )
    console.print()

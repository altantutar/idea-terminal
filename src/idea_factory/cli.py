"""Typer CLI application — all user-facing commands."""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt

from idea_factory.config import DOMAIN_CHOICES, Settings
from idea_factory.db import repository as repo
from idea_factory.db.connection import get_db
from idea_factory.display import (
    display_banner,
    display_costs,
    display_domain_picker,
    display_idea_card,
    display_idea_detail,
    display_ideas_table,
    display_livestream_banner,
    display_persona_picker,
    display_preferences,
    display_provider_detected,
    display_session_resume,
    display_stats,
)
from idea_factory.logging_cfg import setup_logging
from idea_factory.loop import run_loop
from idea_factory.preferences import load_preferences

app = typer.Typer(
    name="idea-factory",
    help="Terminal-native startup idea generator with 6-agent evaluation pipeline.",
    no_args_is_help=True,
)
prefs_app = typer.Typer(help="Manage learned preferences.")
app.add_typer(prefs_app, name="prefs")

console = Console()


@app.command()
def start(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    claude_check: bool = typer.Option(
        False,
        "--claude-check",
        "-cc",
        help="Run Claude Check agent to assess one-shottability",
    ),
) -> None:
    """Start the interactive idea generation loop."""
    import os

    if verbose:
        os.environ["IDEA_FACTORY_VERBOSE"] = "1"

    settings = Settings()
    setup_logging(level=settings.log_level, log_file=settings.log_file)
    display_banner()
    _setup_provider(settings)

    conn = get_db(settings.db_path)
    latest = repo.get_latest_session(conn)
    session_id: int = 0

    if latest:
        display_session_resume(latest)
        resume = Prompt.ask("Continue last session?", choices=["y", "n"], default="y")
        if resume == "y":
            region = latest["region"]
            domains = latest["domains"]
            constraints = latest["constraints"]
            session_id = latest["id"]
        else:
            region = Prompt.ask("Target region/market", default="Global")
            domains = _select_domains()
            constraints = _get_constraints()
            session_id = repo.save_session(conn, region, domains, constraints)
    else:
        region = Prompt.ask("Target region/market", default="Global")
        domains = _select_domains()
        constraints = _get_constraints()
        session_id = repo.save_session(conn, region, domains, constraints)

    conn.close()

    console.print()
    console.rule("[bold green]Starting idea generation loop[/bold green]")
    console.print()

    run_loop(
        region,
        domains,
        constraints,
        settings,
        session_id=session_id,
        claude_check=claude_check,
    )


@app.command()
def livestream(
    persona: Optional[str] = typer.Option(
        None, "--persona", "-p", help="Persona: number, name, @handle, or custom text"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    claude_check: bool = typer.Option(
        False,
        "--claude-check",
        "-cc",
        help="Run Claude Check agent to assess one-shottability",
    ),
) -> None:
    """Start the autonomous livestream mode with an AI taste agent."""
    import os

    from idea_factory.livestream import run_livestream
    from idea_factory.personas import resolve_persona
    from idea_factory.trending import fetch_persona_context

    if verbose:
        os.environ["IDEA_FACTORY_VERBOSE"] = "1"

    settings = Settings()
    setup_logging(level=settings.log_level, log_file=settings.log_file)
    _setup_provider(settings)

    # --- Persona selection ---
    if not persona:
        display_persona_picker()
        persona = Prompt.ask("\nChoose persona", default="1")

    # Resolve @handle with web context
    web_ctx = ""
    if persona.strip().startswith("@"):
        console.print(f"[dim]Searching for {persona.strip()} context...[/dim]")
        web_ctx = fetch_persona_context(persona.strip().lstrip("@"))

    persona_label, persona_description = resolve_persona(persona, web_ctx)

    display_livestream_banner(persona_label)

    console.print()
    console.rule("[bold red]LIVESTREAM STARTING[/bold red]")
    console.print()

    run_livestream(
        settings=settings,
        persona_label=persona_label,
        persona_description=persona_description,
        claude_check=claude_check,
    )


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", "-H", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
) -> None:
    """Launch the web dashboard."""
    try:
        from idea_factory.web import main as web_main
    except ImportError:
        console.print(
            '[red]Web dependencies not installed.[/red]\n[dim]Run: pip install -e ".[web]"[/dim]'
        )
        raise typer.Exit(1)
    console.print(
        f"[bold bright_cyan]Starting web dashboard at http://{host}:{port}[/bold bright_cyan]"
    )
    web_main(host=host, port=port)


@app.command("list")
def list_ideas(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
) -> None:
    """List all generated ideas."""
    settings = _get_settings_quiet()
    conn = get_db(settings.db_path)
    ideas = repo.list_ideas(conn, status)
    conn.close()
    if not ideas:
        console.print("[dim]No ideas found.[/dim]")
        return
    display_ideas_table(ideas)


@app.command()
def show(idea_id: int = typer.Argument(..., help="Idea ID to show")) -> None:
    """Show full detail for a specific idea."""
    settings = _get_settings_quiet()
    conn = get_db(settings.db_path)
    idea = repo.get_idea(conn, idea_id)
    if not idea:
        console.print(f"[red]Idea #{idea_id} not found.[/red]")
        conn.close()
        raise typer.Exit(1)
    outputs = repo.get_agent_outputs(conn, idea_id)
    conn.close()
    display_idea_detail(idea, outputs)


@app.command()
def export(
    idea_id: int = typer.Argument(..., help="Idea ID to export"),
    format: str = typer.Option("json", "--format", "-f", help="Export format: json or md"),
) -> None:
    """Export an idea as JSON or Markdown memo."""
    settings = _get_settings_quiet()
    conn = get_db(settings.db_path)
    idea = repo.get_idea(conn, idea_id)
    if not idea:
        console.print(f"[red]Idea #{idea_id} not found.[/red]")
        conn.close()
        raise typer.Exit(1)
    outputs = repo.get_agent_outputs(conn, idea_id)
    conn.close()

    if format == "json":
        data = {"idea": idea, "agent_outputs": outputs}
        console.print_json(json.dumps(data, default=str))
    elif format == "md":
        _print_markdown_memo(idea, outputs)
    else:
        console.print(f"[red]Unknown format: {format}. Use 'json' or 'md'.[/red]")


@app.command()
def stats() -> None:
    """Show aggregate statistics."""
    settings = _get_settings_quiet()
    conn = get_db(settings.db_path)
    s = repo.get_stats(conn)
    conn.close()
    display_stats(s)


@app.command()
def costs() -> None:
    """Show API token usage and estimated costs."""
    settings = _get_settings_quiet()
    conn = get_db(settings.db_path)
    summary = repo.get_cost_summary(conn)
    conn.close()
    display_costs(summary)


@app.command()
def replay(
    last: int = typer.Option(5, "--last", "-n", help="Number of recent ideas to show"),
) -> None:
    """Replay the last N ideas with scores."""
    settings = _get_settings_quiet()
    conn = get_db(settings.db_path)
    ideas = repo.list_ideas(conn)[:last]
    conn.close()
    if not ideas:
        console.print("[dim]No ideas found.[/dim]")
        return
    for idea in ideas:
        judge_out = None
        # Try to get judge output for display
        conn2 = get_db(settings.db_path)
        outputs = repo.get_agent_outputs(conn2, idea["id"])
        conn2.close()
        for o in outputs:
            if o["agent_name"] == "judge":
                judge_out = o.get("output")
                break
        display_idea_card(idea, judge_out)


# ---------------------------------------------------------------------------
# Preferences subcommands
# ---------------------------------------------------------------------------


@prefs_app.command("show")
def prefs_show() -> None:
    """Display current learned preference weights."""
    settings = _get_settings_quiet()
    conn = get_db(settings.db_path)
    prefs = load_preferences(conn)
    conn.close()
    display_preferences(prefs)


@prefs_app.command("reset")
def prefs_reset() -> None:
    """Reset all learned preferences."""
    settings = _get_settings_quiet()
    conn = get_db(settings.db_path)
    repo.reset_preferences(conn)
    conn.close()
    console.print("[green]Preferences reset.[/green]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROVIDERS = [
    ("anthropic", "Anthropic", "Claude (claude-sonnet-4-6)"),
    ("openai", "OpenAI", "GPT (gpt-4o)"),
    ("gemini", "Google Gemini", "Gemini (gemini-3.1-pro-preview)"),
]


def _prompt_provider_choice() -> str:
    """Show a numbered provider picker and return the selected key."""
    console.print("[bold]Choose your LLM provider:[/bold]\n")
    for i, (_, name, desc) in enumerate(_PROVIDERS, 1):
        console.print(
            f"  [bold bright_cyan]{i}.[/bold bright_cyan]  [bold]{name}[/bold]  [dim]{desc}[/dim]"
        )
    console.print()
    choices = [str(i) for i in range(1, len(_PROVIDERS) + 1)]
    choice = Prompt.ask("Select", choices=choices, default="1")
    return _PROVIDERS[int(choice) - 1][0]


def _setup_provider(settings: Settings) -> None:
    """Auto-detect API keys and configure the LLM provider."""
    has_anthropic = bool(settings.anthropic_api_key)
    has_openai = bool(settings.openai_api_key)
    has_gemini = bool(settings.gemini_api_key)

    available: list[str] = []
    if has_anthropic:
        available.append("anthropic")
    if has_openai:
        available.append("openai")
    if has_gemini:
        available.append("gemini")

    if len(available) == 1:
        provider = available[0]
        settings.set_provider(provider)
        display_provider_detected(provider, settings.model)
    elif len(available) > 1:
        console.print("[green]Found API keys for multiple providers.[/green]\n")
        provider = _prompt_provider_choice()
        settings.set_provider(provider)
        display_provider_detected(provider, settings.model)
    else:
        provider = _prompt_provider_choice()
        settings.set_provider(provider)
        key_name = (
            "ANTHROPIC_API_KEY"
            if provider == "anthropic"
            else "OPENAI_API_KEY"
            if provider == "openai"
            else "GEMINI_API_KEY"
        )
        console.print(f"\n[yellow]No {key_name} found in environment.[/yellow]")
        if provider == "anthropic":
            console.print(
                "[dim]Get your API key at: https://console.anthropic.com/settings/keys[/dim]"
            )
            console.print("[dim]Or set it permanently: export ANTHROPIC_API_KEY=sk-ant-...[/dim]\n")
        elif provider == "openai":
            console.print("[dim]Get your API key at: https://platform.openai.com/api-keys[/dim]")
            console.print("[dim]Or set it permanently: export OPENAI_API_KEY=sk-...[/dim]\n")
        else:
            console.print("[dim]Get your API key at: https://aistudio.google.com/apikey[/dim]")
            console.print("[dim]Or set it permanently: export GEMINI_API_KEY=AIza...[/dim]\n")
        api_key = Prompt.ask(f"Paste your {key_name}", password=True)
        if not api_key.strip():
            console.print("[bold red]API key is required. Exiting.[/bold red]")
            raise typer.Exit(1)
        settings.set_provider(provider, api_key.strip())
        display_provider_detected(provider, settings.model)


def _select_domains() -> list[str]:
    """Interactive domain picker. Returns list of selected domain strings."""
    display_domain_picker()
    domain_input = Prompt.ask(
        "\nSelect domains (comma-separated numbers, or type custom)",
        default="1,4,5",
    )
    domains: list[str] = []
    for part in domain_input.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(DOMAIN_CHOICES):
                domains.append(DOMAIN_CHOICES[idx])
        else:
            domains.append(part)
    if not domains:
        domains = ["saas", "ai/ml"]
    console.print(f"[dim]Selected domains: {', '.join(domains)}[/dim]\n")
    return domains


def _get_constraints() -> str:
    """Prompt user for constraints."""
    return Prompt.ask(
        "Any constraints? (e.g. 'solo founder', 'no hardware', or skip)",
        default="",
    )


def _get_settings_quiet():
    """Get settings without validation (for read-only commands)."""
    from idea_factory.config import Settings

    return Settings()


def _print_markdown_memo(idea: dict, outputs: list[dict]) -> None:
    """Print a markdown-formatted memo for an idea."""
    tags = idea.get("tags", "[]")
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            tags = []

    lines = [
        f"# {idea['name']}",
        "",
        f"> {idea.get('one_liner', '')}",
        "",
        f"**Domain:** {idea.get('domain', '')}  ",
        f"**Region:** {idea.get('region', '')}  ",
        f"**Target user:** {idea.get('target_user', '')}  ",
        f"**Monetization:** {idea.get('monetization', '')}  ",
        f"**Status:** {idea.get('status', '')}  ",
        f"**Composite score:** {idea.get('composite_score', 'N/A')}  ",
        "",
        "## Problem",
        idea.get("problem", ""),
        "",
        "## Solution",
        idea.get("solution", ""),
        "",
    ]

    if tags:
        lines.append(f"**Tags:** {', '.join(tags)}")
        lines.append("")

    for o in outputs:
        agent = o.get("agent_name", "unknown").upper()
        output = o.get("output", {})
        lines.append(f"## {agent} Analysis")
        lines.append("")
        if isinstance(output, dict):
            for k, v in output.items():
                lines.append(f"**{k}:** {v}  ")
        else:
            lines.append(str(output))
        lines.append("")

    console.print("\n".join(lines))

"""All prompt templates for the 6-agent pipeline."""

from __future__ import annotations

SYSTEM_PREFIX = (
    "You are a specialized startup evaluation agent. "
    "You MUST respond with ONLY valid JSON matching the requested schema. "
    "No markdown, no explanation, no preamble — just the JSON object."
)


def creator_prompt(
    region: str,
    domains: list[str],
    constraints: str,
    taste_prefix: str,
    recent_rejections: list[str] | None = None,
    trending_prefix: str = "",
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the Creator agent."""
    system = (
        f"{SYSTEM_PREFIX}\n\n"
        "Your role: CREATOR. You generate novel, opinionated startup ideas. "
        "Each idea should be specific, not generic. Think contrarian."
    )
    rejection_block = ""
    if recent_rejections:
        rejection_block = "\n\nAvoid ideas similar to these recently rejected ones:\n" + "\n".join(
            f"- {r}" for r in recent_rejections[-10:]
        )
    trending_block = ""
    if trending_prefix:
        trending_block = f"\n\n{trending_prefix}"
    user = (
        f"Generate exactly 5 startup ideas.\n\n"
        f"Region/market: {region}\n"
        f"Domains: {', '.join(domains)}\n"
        f"Constraints: {constraints or 'None'}\n"
        f"{taste_prefix}"
        f"{rejection_block}"
        f"{trending_block}\n\n"
        'Respond with JSON: {{"ideas": [{{...}}, ...]}}\n'
        "Each idea must have: name, one_liner, domain, problem, solution, "
        "target_user, monetization, region, tags (list of strings), "
        'inspired_by (list of {{"title": "...", "url": "...", "platform": "..."}} '
        "objects for sources that inspired this idea — can be empty if original)."
    )
    return system, user


def challenger_prompt(idea: dict) -> tuple[str, str]:
    system = (
        f"{SYSTEM_PREFIX}\n\n"
        "Your role: CHALLENGER. You ruthlessly stress-test startup ideas. "
        "Look for fatal flaws, market saturation, regulatory risk, and "
        "technical impossibility. Be harsh but fair."
    )
    user = (
        f"Evaluate this startup idea:\n\n"
        f"Name: {idea['name']}\n"
        f"One-liner: {idea['one_liner']}\n"
        f"Domain: {idea['domain']}\n"
        f"Problem: {idea['problem']}\n"
        f"Solution: {idea['solution']}\n"
        f"Target user: {idea['target_user']}\n"
        f"Monetization: {idea['monetization']}\n"
        f"Region: {idea['region']}\n\n"
        "Respond with JSON: "
        '{{"verdict": "KILL" or "SURVIVE", "fatal_flaws": [...], '
        '"risks": [...], "competitor_overlap": "...", "survival_reason": "..."}}'
    )
    return system, user


def builder_prompt(idea: dict) -> tuple[str, str]:
    system = (
        f"{SYSTEM_PREFIX}\n\n"
        "Your role: BUILDER. You assess technical feasibility and create "
        "a concrete build plan. Think like a pragmatic CTO."
    )
    user = (
        f"Create a build plan for this startup:\n\n"
        f"Name: {idea['name']}\n"
        f"Solution: {idea['solution']}\n"
        f"Target user: {idea['target_user']}\n"
        f"Domain: {idea['domain']}\n\n"
        "Respond with JSON: "
        '{{"buildable": true/false, '
        '"tech_stack": [{{"layer": "...", "choice": "..."}}, ...], '
        '"mvp_scope": "...", '
        '"milestones": [{{"week": "...", "goal": "..."}}, ...], '
        '"build_risk": "..."}}'
    )
    return system, user


def distributor_prompt(idea: dict, build_output: dict) -> tuple[str, str]:
    system = (
        f"{SYSTEM_PREFIX}\n\n"
        "Your role: DISTRIBUTOR. You design the go-to-market strategy. "
        "Think like a growth hacker with deep channel expertise."
    )
    user = (
        f"Design the distribution strategy for:\n\n"
        f"Name: {idea['name']}\n"
        f"One-liner: {idea['one_liner']}\n"
        f"Target user: {idea['target_user']}\n"
        f"Domain: {idea['domain']}\n"
        f"MVP scope: {build_output.get('mvp_scope', 'N/A')}\n\n"
        "Respond with JSON: "
        '{{"primary_channel": "...", '
        '"channels": [{{"channel": "...", "tactic": "...", "expected_cac": "..."}}, ...], '
        '"viral_hook": "...", "launch_strategy": "...", "moat": "..."}}'
    )
    return system, user


def consumer_prompt(idea: dict, build_output: dict, dist_output: dict) -> tuple[str, str]:
    system = (
        f"{SYSTEM_PREFIX}\n\n"
        "Your role: CONSUMER. You simulate real user reactions to the product. "
        "Embody 3-4 different personas and react honestly."
    )
    user = (
        f"Simulate user reactions to this product:\n\n"
        f"Name: {idea['name']}\n"
        f"One-liner: {idea['one_liner']}\n"
        f"Target user: {idea['target_user']}\n"
        f"Solution: {idea['solution']}\n"
        f"Primary channel: {dist_output.get('primary_channel', 'N/A')}\n"
        f"Viral hook: {dist_output.get('viral_hook', 'N/A')}\n\n"
        "Respond with JSON: "
        '{{"personas": [{{"persona": "...", "reaction": "...", '
        '"would_pay": true/false, "objection": "..."}}, ...], '
        '"overall_excitement": 1-10, "willingness_to_pay": 1-10, '
        '"key_objection": "..."}}'
    )
    return system, user


def judge_prompt(
    idea: dict,
    challenger_out: dict,
    builder_out: dict,
    dist_out: dict,
    consumer_out: dict,
) -> tuple[str, str]:
    system = (
        f"{SYSTEM_PREFIX}\n\n"
        "Your role: JUDGE + LEARNER. You synthesize all agent evaluations "
        "and produce a final verdict. Be calibrated and decisive."
    )
    user = (
        f"Judge this startup idea based on all evaluations:\n\n"
        f"== IDEA ==\n"
        f"Name: {idea['name']}\n"
        f"One-liner: {idea['one_liner']}\n"
        f"Domain: {idea['domain']}\n"
        f"Problem: {idea['problem']}\n\n"
        f"== CHALLENGER ==\n"
        f"Verdict: {challenger_out.get('verdict', 'N/A')}\n"
        f"Risks: {challenger_out.get('risks', [])}\n\n"
        f"== BUILDER ==\n"
        f"Buildable: {builder_out.get('buildable', 'N/A')}\n"
        f"Build risk: {builder_out.get('build_risk', 'N/A')}\n\n"
        f"== DISTRIBUTOR ==\n"
        f"Primary channel: {dist_out.get('primary_channel', 'N/A')}\n"
        f"Moat: {dist_out.get('moat', 'N/A')}\n\n"
        f"== CONSUMER ==\n"
        f"Excitement: {consumer_out.get('overall_excitement', 'N/A')}/10\n"
        f"WTP: {consumer_out.get('willingness_to_pay', 'N/A')}/10\n"
        f"Key objection: {consumer_out.get('key_objection', 'N/A')}\n\n"
        "Respond with JSON: "
        '{{"scores": {{"novelty": 1-10, "feasibility": 1-10, '
        '"market_potential": 1-10, "defensibility": 1-10, "excitement": 1-10}}, '
        '"composite_score": 0.0-10.0, "verdict": "WINNER"/"CONTENDER"/"PASS", '
        '"one_line_summary": "...", "archetype": "..."}}'
    )
    return system, user


# ---------------------------------------------------------------------------
# Claude Check prompt
# ---------------------------------------------------------------------------


def claude_check_prompt(idea: dict, judge_output: dict, builder_output: dict) -> tuple[str, str]:
    """Return (system, user) prompts for the Claude Check agent."""
    scores = judge_output.get("scores", {})
    tech_stack = builder_output.get("tech_stack", [])
    stack_str = (
        ", ".join(
            f"{s.get('layer', '')}: {s.get('choice', '')}" if isinstance(s, dict) else str(s)
            for s in tech_stack
        )
        if tech_stack
        else "N/A"
    )

    system = (
        f"{SYSTEM_PREFIX}\n\n"
        "Your role: CLAUDE CHECK AGENT. You assess whether any Claude product "
        "(Claude Code, Claude Chat, Artifacts, MCP servers, Claude API) could "
        "build this startup idea in a single session (~2 hours).\n\n"
        "You know Claude's capabilities intimately:\n"
        "- Claude Code: Can scaffold full-stack apps, write backend/frontend, "
        "set up databases, deploy to Vercel/Railway, create CLI tools.\n"
        "- Claude Chat + Artifacts: Can build React apps, dashboards, data "
        "visualizations, landing pages, and interactive prototypes.\n"
        "- Claude API with MCP: Can orchestrate multi-tool workflows, connect "
        "to databases, call external APIs, manage file systems.\n"
        "- Claude API (direct): Can power chatbots, content generation, "
        "classification, extraction, and analysis pipelines.\n\n"
        "Be honest about what CAN and CANNOT be one-shotted. A CRUD app with "
        "auth? One-shottable. A real-time collaborative editor with CRDT? Needs work. "
        "A startup requiring proprietary data, hardware, or regulatory approval? Not feasible.\n\n"
        "The defensibility question is key: if Claude can build the MVP in 2 hours, "
        "so can anyone with Claude — what then is the startup's moat?"
    )
    user = (
        f"Assess whether Claude can one-shot this startup idea:\n\n"
        f"== IDEA ==\n"
        f"Name: {idea.get('name', 'N/A')}\n"
        f"One-liner: {idea.get('one_liner', 'N/A')}\n"
        f"Domain: {idea.get('domain', 'N/A')}\n"
        f"Problem: {idea.get('problem', 'N/A')}\n"
        f"Solution: {idea.get('solution', 'N/A')}\n"
        f"Target user: {idea.get('target_user', 'N/A')}\n"
        f"Monetization: {idea.get('monetization', 'N/A')}\n\n"
        f"== BUILD PLAN ==\n"
        f"Buildable: {builder_output.get('buildable', 'N/A')}\n"
        f"Tech stack: {stack_str}\n"
        f"MVP scope: {builder_output.get('mvp_scope', 'N/A')}\n"
        f"Build risk: {builder_output.get('build_risk', 'N/A')}\n\n"
        f"== JUDGE SCORES ==\n"
        f"Feasibility: {scores.get('feasibility', '?')}/10  "
        f"Defensibility: {scores.get('defensibility', '?')}/10\n"
        f"Composite: {judge_output.get('composite_score', '?')}/10  "
        f"Verdict: {judge_output.get('verdict', 'N/A')}\n\n"
        "Respond with JSON:\n"
        '{{"verdict": "one_shottable"/"needs_work"/"not_feasible", '
        '"claude_product": "which Claude product(s)", '
        '"time_estimate": "~X hours/days or not applicable", '
        '"what_it_builds": "what Claude produces in one session", '
        '"what_it_cant": "what remains unsolved", '
        '"defensibility_note": "moat implication"}}'
    )
    return system, user


# ---------------------------------------------------------------------------
# Reflection prompts
# ---------------------------------------------------------------------------


def challenger_reflection_prompt(idea: dict, challenger_output: dict) -> tuple[str, str]:
    """Return (system, user) prompts to critique a Challenger output."""
    system = (
        f"{SYSTEM_PREFIX}\n\n"
        "Your role: REFLECTION AUDITOR for the Challenger agent. "
        "You review the Challenger's output and check whether its reasoning "
        "is rigorous. You must respond with ONLY valid JSON."
    )
    user = (
        "Review the Challenger agent's evaluation of this idea.\n\n"
        f"== IDEA ==\n"
        f"Name: {idea.get('name', 'N/A')}\n"
        f"One-liner: {idea.get('one_liner', 'N/A')}\n"
        f"Domain: {idea.get('domain', 'N/A')}\n"
        f"Problem: {idea.get('problem', 'N/A')}\n"
        f"Solution: {idea.get('solution', 'N/A')}\n"
        f"Target user: {idea.get('target_user', 'N/A')}\n"
        f"Monetization: {idea.get('monetization', 'N/A')}\n"
        f"Region: {idea.get('region', 'N/A')}\n\n"
        f"== CHALLENGER OUTPUT ==\n"
        f"Verdict: {challenger_output.get('verdict', 'N/A')}\n"
        f"Fatal flaws: {challenger_output.get('fatal_flaws', [])}\n"
        f"Risks: {challenger_output.get('risks', [])}\n"
        f"Competitor overlap: {challenger_output.get('competitor_overlap', '')}\n"
        f"Survival reason: {challenger_output.get('survival_reason', '')}\n\n"
        "Check against these principles:\n"
        '1. Are listed "fatal flaws" truly fatal (regulatory impossibility, '
        "physical constraint, proven market failure) or are they actually "
        "surmountable risks mislabeled as fatal?\n"
        "2. Were the idea's novel aspects genuinely considered, or dismissed "
        "via shallow pattern matching (e.g. 'X already exists')?\n"
        "3. Are competitor comparisons specific (named companies, concrete "
        "overlap) or vague hand-waving?\n"
        "4. Is the verdict strength proportional to the evidence? A KILL "
        "requires genuinely fatal issues, not just challenges.\n\n"
        "Respond with JSON: "
        '{{"is_satisfactory": true/false, "critique": "...", '
        '"weaknesses": ["..."], "suggested_focus": "..."}}'
    )
    return system, user


def taste_prompt(
    idea: dict,
    judge_output: dict,
    persona_description: str,
) -> tuple[str, str]:
    """Return (system, user) prompts for the Taste Agent (AI persona feedback)."""
    scores = judge_output.get("scores", {})
    system = (
        f"{SYSTEM_PREFIX}\n\n"
        "Your role: TASTE AGENT. You embody a specific persona and give your "
        "honest gut reaction to a startup idea. You are NOT neutral — you have "
        "strong opinions shaped by your persona. React authentically."
    )
    user = (
        f"You are: {persona_description}\n\n"
        f"Evaluate this startup idea from YOUR perspective:\n\n"
        f"== IDEA ==\n"
        f"Name: {idea.get('name', 'N/A')}\n"
        f"One-liner: {idea.get('one_liner', 'N/A')}\n"
        f"Domain: {idea.get('domain', 'N/A')}\n"
        f"Problem: {idea.get('problem', 'N/A')}\n"
        f"Solution: {idea.get('solution', 'N/A')}\n"
        f"Target user: {idea.get('target_user', 'N/A')}\n"
        f"Monetization: {idea.get('monetization', 'N/A')}\n\n"
        f"== JUDGE SCORES ==\n"
        f"Novelty: {scores.get('novelty', '?')}/10  "
        f"Feasibility: {scores.get('feasibility', '?')}/10  "
        f"Market: {scores.get('market_potential', '?')}/10\n"
        f"Composite: {judge_output.get('composite_score', '?')}/10  "
        f"Verdict: {judge_output.get('verdict', 'N/A')}\n"
        f"Summary: {judge_output.get('one_line_summary', '')}\n\n"
        "Give your reaction as this persona. Be opinionated!\n\n"
        "Respond with JSON:\n"
        '{{"decision": "love"/"like"/"meh"/"hate", '
        '"rating": 1-10, '
        '"tags": ["strengths or weaknesses you noticed"], '
        '"note": "your persona\'s honest take in 1-2 sentences"}}'
    )
    return system, user


def judge_reflection_prompt(idea: dict, judge_output: dict) -> tuple[str, str]:
    """Return (system, user) prompts to critique a Judge output."""
    scores = judge_output.get("scores", {})
    system = (
        f"{SYSTEM_PREFIX}\n\n"
        "Your role: REFLECTION AUDITOR for the Judge agent. "
        "You review the Judge's scoring and verdict for internal consistency "
        "and calibration. You must respond with ONLY valid JSON."
    )
    user = (
        "Review the Judge agent's evaluation of this idea.\n\n"
        f"== IDEA ==\n"
        f"Name: {idea.get('name', 'N/A')}\n"
        f"One-liner: {idea.get('one_liner', 'N/A')}\n"
        f"Domain: {idea.get('domain', 'N/A')}\n"
        f"Problem: {idea.get('problem', 'N/A')}\n\n"
        f"== JUDGE OUTPUT ==\n"
        f"Scores: novelty={scores.get('novelty', '?')}, "
        f"feasibility={scores.get('feasibility', '?')}, "
        f"market_potential={scores.get('market_potential', '?')}, "
        f"defensibility={scores.get('defensibility', '?')}, "
        f"excitement={scores.get('excitement', '?')}\n"
        f"Composite score: {judge_output.get('composite_score', '?')}\n"
        f"Verdict: {judge_output.get('verdict', 'N/A')}\n"
        f"Summary: {judge_output.get('one_line_summary', '')}\n"
        f"Archetype: {judge_output.get('archetype', '')}\n\n"
        "Check against these principles:\n"
        "1. Is every dimension score justified by actual merits of the idea, "
        "not inflated or deflated without reason?\n"
        "2. Is the composite score dominated by a single extreme dimension "
        "while others are ignored?\n"
        "3. Does the verdict match the composite score? A composite around "
        "4.0 should not be WINNER; a composite around 8.5 should not be PASS.\n"
        "4. Is the one-line summary insightful and specific to this idea, "
        "or is it generic boilerplate?\n"
        "5. Are the individual dimension scores internally consistent "
        "(e.g. high feasibility shouldn't coexist with a 'technically "
        "impossible' note)?\n\n"
        "Respond with JSON: "
        '{{"is_satisfactory": true/false, "critique": "...", '
        '"weaknesses": ["..."], "suggested_focus": "..."}}'
    )
    return system, user

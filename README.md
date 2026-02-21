# Idea Factory

Terminal-native startup idea generator with a multi-agent evaluation pipeline. Each idea passes through a gauntlet of specialized AI agents that generate, stress-test, build-plan, distribute, simulate user reactions, and judge startup concepts — all from your terminal.

## Features

- **6-Agent Pipeline** — Creator, Challenger, Builder, Distributor, Consumer, Judge
- **Claude Check Agent** — Optional `--claude-check` flag assesses whether Claude can one-shot the idea, serving as a defensibility filter
- **Reflexion** — Self-critique loops on Challenger and Judge outputs for higher quality evaluations
- **Preference Learning** — The system learns your taste over time and tailors future ideas
- **Livestream Mode** — Fully autonomous mode with an AI taste agent replacing human feedback
- **Persona System** — Choose from famous founders, archetypes, or custom personas for the taste agent
- **Trending Integration** — Injects real-time trending topics into idea generation
- **Session Persistence** — SQLite-backed storage for ideas, agent outputs, feedback, and preferences

## Installation

```bash
# Clone the repo
git clone https://github.com/altantutar/idea-terminal.git
cd idea-terminal

# Install in development mode
pip install -e .
```

### Requirements

- Python 3.11+
- An API key for either [Anthropic](https://console.anthropic.com/settings/keys) or [OpenAI](https://platform.openai.com/api-keys)

```bash
# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...
```

## Usage

### Interactive Mode

```bash
idea-factory start
```

Launches the interactive loop: pick domains, set constraints, and evaluate ideas with your own feedback.

```bash
idea-factory start --claude-check
```

Same as above, but after each finalist is judged, the Claude Check agent assesses whether the idea can be one-shotted by Claude — a quick defensibility sanity check.

### Livestream Mode

```bash
idea-factory livestream
idea-factory livestream -p "elon musk"
idea-factory livestream --claude-check
```

Fully autonomous mode. An AI persona replaces human feedback. Runs continuously until Ctrl+C.

### Other Commands

```bash
idea-factory list                  # List all generated ideas
idea-factory list --status winner  # Filter by status
idea-factory show <id>             # Show full detail for an idea
idea-factory export <id>           # Export as JSON
idea-factory export <id> -f md     # Export as Markdown
idea-factory stats                 # Aggregate statistics
idea-factory replay                # Replay last 5 ideas with scores
idea-factory prefs show            # View learned preferences
idea-factory prefs reset           # Reset preferences
```

## Pipeline

```
CREATOR ──> CHALLENGER ──> BUILDER ──> DISTRIBUTOR ──> CONSUMER ──> JUDGE ──> [CLAUDE CHECK] ──> FEEDBACK
  │              │                                                                │
  │         kills weak                                                    optional flag
  │           ideas                                                      --claude-check
  │
  └── informed by preferences, rejections, trending topics
```

1. **Creator** — Generates 5 startup ideas per loop, informed by taste preferences and trending topics
2. **Challenger** — Stress-tests each idea for fatal flaws (with reflexion)
3. **Builder** — Assesses technical feasibility and produces a build plan
4. **Distributor** — Designs go-to-market strategy with channels, viral hooks, and moat
5. **Consumer** — Simulates 3-4 user personas reacting to the product
6. **Judge** — Synthesizes all evaluations into scores and a final verdict (with reflexion)
7. **Claude Check** *(optional)* — Evaluates if Claude can one-shot the MVP, highlighting defensibility implications
8. **Feedback** — Human feedback (interactive) or AI taste agent (livestream)

## Claude Check Agent

Activated with `--claude-check` / `-cc`. Runs after the Judge for each finalist and answers:

- **Verdict** — `one_shottable` / `needs_work` / `not_feasible`
- **Claude Product** — Which Claude product could build it (Code, Chat + Artifacts, API with MCP)
- **Time Estimate** — How long it would take
- **What It Builds** — What Claude can produce in a single session
- **What It Can't** — What remains unsolved (data moats, distribution, regulatory)
- **Defensibility Note** — If Claude can build it in 2 hours, so can anyone — what's the moat?

## Project Structure

```
src/idea_factory/
├── agents/
│   ├── base.py           # BaseAgent class
│   ├── builder.py        # Builder agent
│   ├── challenger.py     # Challenger agent
│   ├── claude_check.py   # Claude Check agent
│   ├── consumer.py       # Consumer agent
│   ├── creator.py        # Creator agent
│   ├── distributor.py    # Distributor agent
│   ├── judge.py          # Judge agent
│   └── taste.py          # Taste agent (livestream)
├── db/
│   ├── connection.py     # SQLite connection
│   └── repository.py     # CRUD operations
├── llm/
│   ├── anthropic.py      # Anthropic provider
│   ├── base.py           # LLMProvider base
│   ├── factory.py        # Provider factory
│   └── openai.py         # OpenAI provider
├── cli.py                # Typer CLI commands
├── config.py             # Settings
├── display.py            # Rich terminal rendering
├── livestream.py         # Autonomous loop
├── loop.py               # Interactive loop
├── models.py             # Pydantic models
├── personas.py           # Persona definitions
├── preferences.py        # Preference learning
├── prompts.py            # All prompt templates
├── reflexion.py          # Self-critique loop
└── trending.py           # Trending topic integration
```

## License

MIT

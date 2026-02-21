# Contributing to Idea Factory

Thanks for your interest in contributing! This project is open to contributions of all kinds — bug fixes, new agents, better prompts, new inspiration sources, and more.

## Getting Started

1. Fork the repository
2. Clone your fork:

```bash
git clone https://github.com/<your-username>/idea-terminal.git
cd idea-terminal
```

3. Create a virtual environment and install in dev mode:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

4. Set up your API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...
```

5. Verify everything works:

```bash
idea-factory start
```

## Making Changes

1. Create a branch from `main`:

```bash
git checkout -b your-feature-name
```

2. Make your changes
3. Test manually by running the pipeline (`idea-factory start` or `idea-factory livestream`)
4. Commit with a clear message describing what and why

## Pull Request Process

1. Push your branch and open a PR against `main`
2. Describe what your change does and why
3. Link any related issues
4. Keep PRs focused — one feature or fix per PR

## What to Contribute

Here are some areas where contributions are especially welcome:

- **New agents** — Add agents to the pipeline (see `src/idea_factory/agents/` for examples)
- **Better prompts** — Improve prompt templates in `src/idea_factory/prompts.py`
- **Inspiration sources** — Add new trending sources in `src/idea_factory/trending.py`
- **Personas** — Add new persona definitions in `src/idea_factory/personas.py`
- **Bug fixes** — If something breaks, fix it
- **Tests** — The project currently has no test suite — adding one would be a great contribution

## Code Style

- Python 3.11+
- Type hints where practical
- Keep functions focused and files organized by responsibility
- Follow the existing patterns in the codebase

## Reporting Issues

Use GitHub Issues for bug reports and feature requests. Include:

- Steps to reproduce (for bugs)
- Expected vs actual behavior
- Python version and OS
- Relevant error output

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

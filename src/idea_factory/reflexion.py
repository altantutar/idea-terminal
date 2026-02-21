"""Reflexion wrapper — self-critique loop for any agent."""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel
from rich.console import Console

from idea_factory.models import ReflectionOutput

console = Console(stderr=True)


def run_with_reflexion(
    agent: object,
    context: dict,
    reflection_prompt_fn: Callable[[dict, dict], tuple[str, str]],
    max_rounds: int = 2,
) -> BaseModel:
    """Run an agent with reflexion-based self-critique.

    1. Execute ``agent.run(context)`` to get initial output.
    2. Use *reflection_prompt_fn* to build a critique prompt and ask the LLM
       whether the output is satisfactory.
    3. If unsatisfactory, re-run the agent with the critique injected into
       the user prompt.
    4. Repeat up to *max_rounds* times, then return the best output.

    Falls back gracefully: any ``ValueError`` during reflection or re-run
    keeps the current output unchanged.
    """
    # Initial pass — identical to calling agent.run(context) directly.
    output = agent.run(context)  # type: ignore[union-attr]

    for round_num in range(1, max_rounds + 1):
        # Build the reflection prompt from the current output.
        try:
            ref_system, ref_user = reflection_prompt_fn(
                context, output.model_dump()
            )
        except Exception:
            break

        # Ask the LLM to critique the output.
        try:
            reflection: ReflectionOutput = agent.provider.generate(  # type: ignore[union-attr]
                ref_system, ref_user, ReflectionOutput
            )
        except ValueError:
            console.print(
                f"  [dim]Reflection parse failed (round {round_num}), keeping current output[/dim]"
            )
            break

        if reflection.is_satisfactory:
            console.print(
                f"  [dim]Reflection round {round_num}: satisfactory[/dim]"
            )
            break

        # Not satisfactory — re-run the agent with critique appended.
        console.print(
            f"  [dim]Reflection round {round_num}: re-running "
            f"({', '.join(reflection.weaknesses) or reflection.critique[:60]})[/dim]"
        )

        try:
            system_prompt, user_prompt = agent.build_prompts(context)  # type: ignore[union-attr]
            critique_block = (
                "\n\n[REFLECTION FEEDBACK — address these issues]\n"
                f"Critique: {reflection.critique}\n"
                f"Weaknesses: {'; '.join(reflection.weaknesses)}\n"
                f"Focus on: {reflection.suggested_focus}\n"
                "[END REFLECTION FEEDBACK]"
            )
            augmented_user = user_prompt + critique_block
            output = agent.provider.generate(  # type: ignore[union-attr]
                system_prompt, augmented_user, agent.output_model()  # type: ignore[union-attr]
            )
        except ValueError:
            console.print(
                f"  [dim]Re-run parse failed (round {round_num}), keeping previous output[/dim]"
            )
            break

    return output

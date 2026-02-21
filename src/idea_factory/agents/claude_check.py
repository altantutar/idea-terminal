"""CLAUDE CHECK agent — can Claude one-shot this startup idea?"""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from idea_factory.models import ClaudeCheckOutput
from idea_factory.prompts import claude_check_prompt

from .base import BaseAgent


class ClaudeCheckAgent(BaseAgent):
    name = "claude_check"

    def build_prompts(self, context: dict) -> tuple[str, str]:
        return claude_check_prompt(
            idea=context["idea"],
            judge_output=context["judge_output"],
            builder_output=context["builder_output"],
        )

    @classmethod
    def output_model(cls) -> Type[BaseModel]:
        return ClaudeCheckOutput

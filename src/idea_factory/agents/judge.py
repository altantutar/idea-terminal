"""JUDGE agent — final scoring and verdict."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from idea_factory.models import JudgeOutput
from idea_factory.prompts import judge_prompt

from .base import BaseAgent


class JudgeAgent(BaseAgent):
    name = "judge"

    def build_prompts(self, context: dict) -> tuple[str, str]:
        return judge_prompt(
            idea=context["idea"],
            challenger_out=context["challenger_out"],
            builder_out=context["builder_out"],
            dist_out=context["dist_out"],
            consumer_out=context["consumer_out"],
            historical_concepts=context.get("historical_concepts"),
        )

    @classmethod
    def output_model(cls) -> Type[BaseModel]:
        return JudgeOutput

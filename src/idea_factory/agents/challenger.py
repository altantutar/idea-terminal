"""CHALLENGER agent — stress-tests ideas for fatal flaws."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from idea_factory.models import ChallengerOutput
from idea_factory.prompts import challenger_prompt

from .base import BaseAgent


class ChallengerAgent(BaseAgent):
    name = "challenger"

    def build_prompts(self, context: dict) -> tuple[str, str]:
        return challenger_prompt(idea=context["idea"])

    @classmethod
    def output_model(cls) -> Type[BaseModel]:
        return ChallengerOutput

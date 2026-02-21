"""TASTE agent — AI persona that replaces human feedback in livestream mode."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from idea_factory.models import TasteFeedback
from idea_factory.prompts import taste_prompt

from .base import BaseAgent


class TasteAgent(BaseAgent):
    name = "taste"

    def build_prompts(self, context: dict) -> tuple[str, str]:
        return taste_prompt(
            idea=context["idea"],
            judge_output=context["judge_output"],
            persona_description=context["persona_description"],
        )

    @classmethod
    def output_model(cls) -> Type[BaseModel]:
        return TasteFeedback

"""REFINER agent — expands a raw user pitch into a structured IdeaSchema."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from idea_factory.models import IdeaSchema
from idea_factory.prompts import refiner_prompt

from .base import BaseAgent


class RefinerAgent(BaseAgent):
    name = "refiner"

    def build_prompts(self, context: dict) -> tuple[str, str]:
        return refiner_prompt(
            raw_pitch=context["raw_pitch"],
            region=context.get("region", "Global"),
            domain_hint=context.get("domain_hint", ""),
        )

    @classmethod
    def output_model(cls) -> Type[BaseModel]:
        return IdeaSchema

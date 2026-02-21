"""BUILDER agent — assesses feasibility and creates build plan."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from idea_factory.models import BuilderOutput
from idea_factory.prompts import builder_prompt

from .base import BaseAgent


class BuilderAgent(BaseAgent):
    name = "builder"

    def build_prompts(self, context: dict) -> tuple[str, str]:
        return builder_prompt(idea=context["idea"])

    @classmethod
    def output_model(cls) -> Type[BaseModel]:
        return BuilderOutput

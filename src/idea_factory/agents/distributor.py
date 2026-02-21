"""DISTRIBUTOR agent — designs go-to-market strategy."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from idea_factory.models import DistributorOutput
from idea_factory.prompts import distributor_prompt

from .base import BaseAgent


class DistributorAgent(BaseAgent):
    name = "distributor"

    def build_prompts(self, context: dict) -> tuple[str, str]:
        return distributor_prompt(
            idea=context["idea"],
            build_output=context["build_output"],
        )

    @classmethod
    def output_model(cls) -> Type[BaseModel]:
        return DistributorOutput

"""CONSUMER agent — simulates real user reactions."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from idea_factory.models import ConsumerOutput
from idea_factory.prompts import consumer_prompt

from .base import BaseAgent


class ConsumerAgent(BaseAgent):
    name = "consumer"

    def build_prompts(self, context: dict) -> tuple[str, str]:
        return consumer_prompt(
            idea=context["idea"],
            build_output=context["build_output"],
            dist_output=context["dist_output"],
        )

    @classmethod
    def output_model(cls) -> Type[BaseModel]:
        return ConsumerOutput

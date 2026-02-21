"""Base agent class for the evaluation pipeline."""

from __future__ import annotations

import logging
from typing import Type, TypeVar

from pydantic import BaseModel

from idea_factory.llm.base import LLMProvider

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger("idea_factory.agents")


class BaseAgent:
    """Every pipeline agent inherits from this."""

    name: str = "base"

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider
        self.last_usage: dict = {}

    def run(self, context: dict) -> BaseModel:
        """Build prompts, call LLM, parse and return typed output."""
        system_prompt, user_prompt = self.build_prompts(context)
        result = self.provider.generate(system_prompt, user_prompt, self.output_model())
        self.last_usage = self.provider.get_last_usage()
        logger.debug(
            "%s tokens: input=%d output=%d",
            self.name,
            self.last_usage.get("input_tokens", 0),
            self.last_usage.get("output_tokens", 0),
        )
        return result

    def build_prompts(self, context: dict) -> tuple[str, str]:
        raise NotImplementedError

    @classmethod
    def output_model(cls) -> Type[BaseModel]:
        raise NotImplementedError

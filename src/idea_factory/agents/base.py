"""Base agent class for the evaluation pipeline."""

from __future__ import annotations

from typing import Type, TypeVar

from pydantic import BaseModel

from idea_factory.llm.base import LLMProvider

T = TypeVar("T", bound=BaseModel)


class BaseAgent:
    """Every pipeline agent inherits from this."""

    name: str = "base"

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def run(self, context: dict) -> BaseModel:
        """Build prompts, call LLM, parse and return typed output."""
        system_prompt, user_prompt = self.build_prompts(context)
        return self.provider.generate(system_prompt, user_prompt, self.output_model())

    def build_prompts(self, context: dict) -> tuple[str, str]:
        raise NotImplementedError

    @classmethod
    def output_model(cls) -> Type[BaseModel]:
        raise NotImplementedError

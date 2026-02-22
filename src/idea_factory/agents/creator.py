"""CREATOR agent — generates batches of startup ideas."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from idea_factory.models import CreatorOutput
from idea_factory.prompts import creator_prompt

from .base import BaseAgent


class CreatorAgent(BaseAgent):
    name = "creator"

    def build_prompts(self, context: dict) -> tuple[str, str]:
        return creator_prompt(
            region=context["region"],
            domains=context["domains"],
            constraints=context.get("constraints", ""),
            taste_prefix=context.get("taste_prefix", ""),
            recent_rejections=context.get("recent_rejections"),
            trending_prefix=context.get("trending_prefix", ""),
            domain_niches_hint=context.get("domain_niches_hint", ""),
        )

    @classmethod
    def output_model(cls) -> Type[BaseModel]:
        return CreatorOutput

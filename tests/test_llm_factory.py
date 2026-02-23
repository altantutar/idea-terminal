"""Tests for LLM provider factory."""

from __future__ import annotations

import os
from unittest import mock

from idea_factory.config import Settings
from idea_factory.llm.anthropic import AnthropicProvider
from idea_factory.llm.factory import get_provider
from idea_factory.llm.gemini import GeminiProvider
from idea_factory.llm.openai import OpenAIProvider


def test_factory_returns_anthropic_provider():
    env = {"IDEA_FACTORY_LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "a-test"}
    with mock.patch.dict(os.environ, env, clear=False):
        settings = Settings()
        provider = get_provider(settings)
        assert isinstance(provider, AnthropicProvider)


def test_factory_returns_openai_provider():
    env = {"IDEA_FACTORY_LLM_PROVIDER": "openai", "OPENAI_API_KEY": "o-test"}
    with mock.patch.dict(os.environ, env, clear=False):
        settings = Settings()
        provider = get_provider(settings)
        assert isinstance(provider, OpenAIProvider)


def test_factory_returns_gemini_provider():
    env = {"IDEA_FACTORY_LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "g-test"}
    with mock.patch.dict(os.environ, env, clear=False):
        settings = Settings()
        provider = get_provider(settings)
        assert isinstance(provider, GeminiProvider)

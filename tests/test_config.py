"""Tests for Settings configuration and environment variable handling."""

from __future__ import annotations

import os
from unittest import mock

import pytest

from idea_factory.config import Settings, _env_float, _env_int


class TestEnvHelpers:
    def test_env_int_default(self):
        assert _env_int("NONEXISTENT_VAR_12345", 42) == 42

    def test_env_int_from_env(self):
        with mock.patch.dict(os.environ, {"TEST_INT": "7"}):
            assert _env_int("TEST_INT", 42) == 7

    def test_env_int_invalid_falls_back(self):
        with mock.patch.dict(os.environ, {"TEST_INT": "not_a_number"}):
            assert _env_int("TEST_INT", 42) == 42

    def test_env_float_default(self):
        assert _env_float("NONEXISTENT_VAR_12345", 3.14) == 3.14

    def test_env_float_from_env(self):
        with mock.patch.dict(os.environ, {"TEST_FLOAT": "2.5"}):
            assert _env_float("TEST_FLOAT", 3.14) == 2.5

    def test_env_float_invalid_falls_back(self):
        with mock.patch.dict(os.environ, {"TEST_FLOAT": "abc"}):
            assert _env_float("TEST_FLOAT", 3.14) == 3.14


class TestSettings:
    def test_defaults(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            # Need at least the provider env or it defaults to anthropic
            s = Settings()
            assert s.llm_provider == "anthropic"
            assert s.model == "claude-sonnet-4-6"
            assert s.top_k == 2
            assert s.max_winners == 10
            assert s.max_retries == 2
            assert s.reflexion_max_rounds == 2
            assert s.trending_cache_ttl == 600
            assert s.pace_between_ideas == 2.0
            assert s.pace_between_loops == 5.0
            assert s.log_level == "INFO"
            assert s.log_file is None

    def test_custom_tuning_from_env(self):
        env = {
            "IDEA_FACTORY_TOP_K": "5",
            "IDEA_FACTORY_MAX_WINNERS": "20",
            "IDEA_FACTORY_MAX_RETRIES": "3",
            "IDEA_FACTORY_REFLEXION_MAX_ROUNDS": "4",
            "IDEA_FACTORY_TRENDING_CACHE_TTL": "1200",
            "IDEA_FACTORY_PACE_BETWEEN_IDEAS": "1.5",
            "IDEA_FACTORY_PACE_BETWEEN_LOOPS": "3.0",
            "IDEA_FACTORY_LOG_LEVEL": "DEBUG",
            "IDEA_FACTORY_LOG_FILE": "/tmp/test.log",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            s = Settings()
            assert s.top_k == 5
            assert s.max_winners == 20
            assert s.max_retries == 3
            assert s.reflexion_max_rounds == 4
            assert s.trending_cache_ttl == 1200
            assert s.pace_between_ideas == 1.5
            assert s.pace_between_loops == 3.0
            assert s.log_level == "DEBUG"
            assert s.log_file == "/tmp/test.log"

    def test_openai_provider(self):
        env = {"IDEA_FACTORY_LLM_PROVIDER": "openai"}
        with mock.patch.dict(os.environ, env, clear=False):
            s = Settings()
            assert s.llm_provider == "openai"
            assert s.model == "gpt-4o"

    def test_invalid_provider(self):
        env = {"IDEA_FACTORY_LLM_PROVIDER": "invalid"}
        with mock.patch.dict(os.environ, env, clear=False):
            with pytest.raises(ValueError, match="Unsupported LLM provider"):
                Settings()

    def test_verbose_flag(self):
        for val in ("1", "true", "yes", "True", "YES"):
            with mock.patch.dict(os.environ, {"IDEA_FACTORY_VERBOSE": val}, clear=False):
                s = Settings()
                assert s.verbose is True

        for val in ("0", "false", "no", ""):
            with mock.patch.dict(os.environ, {"IDEA_FACTORY_VERBOSE": val}, clear=False):
                s = Settings()
                assert s.verbose is False

    def test_set_provider(self):
        s = Settings()
        s.set_provider("openai", "sk-test")
        assert s.llm_provider == "openai"
        assert s.openai_api_key == "sk-test"

    def test_set_provider_invalid(self):
        s = Settings()
        with pytest.raises(ValueError, match="Unsupported provider"):
            s.set_provider("gemini")

    def test_active_api_key(self):
        s = Settings()
        s.anthropic_api_key = "key-a"
        s.openai_api_key = "key-o"
        s.llm_provider = "anthropic"
        assert s.active_api_key() == "key-a"
        s.llm_provider = "openai"
        assert s.active_api_key() == "key-o"

    def test_validate_missing_anthropic_key(self):
        s = Settings()
        s.llm_provider = "anthropic"
        s.anthropic_api_key = None
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            s.validate()

    def test_validate_missing_openai_key(self):
        s = Settings()
        s.llm_provider = "openai"
        s.openai_api_key = None
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            s.validate()

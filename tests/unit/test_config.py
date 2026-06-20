"""Tests for config module — H6 (empty string) and C3 (int parsing)."""
from __future__ import annotations

import os
from unittest.mock import patch
from repomind.utils.config import load_config, _safe_int, AppConfig


class TestSafeInt:
    """C3: _safe_int should handle invalid integers gracefully."""

    def test_valid_int(self):
        assert _safe_int("42", 0) == 42

    def test_empty_string_returns_default(self):
        assert _safe_int("", 60) == 60

    def test_non_numeric_returns_default(self):
        assert _safe_int("abc", 4) == 4

    def test_none_returns_default(self):
        assert _safe_int(None, 10) == 10

    def test_float_string_returns_default(self):
        assert _safe_int("3.14", 0) == 0

    def test_negative_int(self):
        assert _safe_int("-1", 0) == -1


class TestLoadConfig:
    """H6: .env empty string should take precedence over env vars."""

    def test_default_config(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config(env_file="/nonexistent/.env")
            assert isinstance(config, AppConfig)
            assert config.llm.provider == "litellm"

    def test_env_vars_override_defaults(self):
        with patch.dict(os.environ, {"REPOMIND_LLM_MODEL": "gpt-4"}, clear=True):
            config = load_config(env_file="/nonexistent/.env")
            assert config.llm.model == "gpt-4"

    def test_empty_string_in_env_is_preserved(self, tmp_path):
        """H6: Empty string should NOT fall through to os.environ."""
        with patch.dict(os.environ, {"REPOMIND_LLM_BASE_URL": "http://fallback"}, clear=True):
            env_file = tmp_path / ".env"
            env_file.write_text('REPOMIND_LLM_BASE_URL=\n')
            config = load_config(env_file=str(env_file))
            assert config.llm.base_url == ""

    def test_invalid_timeout_uses_default(self):
        """C3: Invalid integer should not crash."""
        with patch.dict(os.environ, {"REPOMIND_SANDBOX_TIMEOUT": "abc"}, clear=True):
            config = load_config(env_file="/nonexistent/.env")
            assert config.sandbox.timeout == 60

    def test_invalid_max_workers_uses_default(self):
        with patch.dict(os.environ, {"REPOMIND_MAX_WORKERS": ""}, clear=True):
            config = load_config(env_file="/nonexistent/.env")
            assert config.max_workers == 4

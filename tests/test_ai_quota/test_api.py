"""Tests for the public ai_quota API: get_usage() and is_exhausted()."""
from unittest.mock import patch

import pytest

import ai_quota


class TestGetUsage:
    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            ai_quota.get_usage("openai")

    def test_cached_calls_read_cache(self):
        fake = [{"label": "session", "percent": 50, "reset_ts": None, "cost": ""}]
        with patch("ai_quota.claude.read_cache", return_value=fake) as m:
            result = ai_quota.get_usage("claude", cached=True)
        m.assert_called_once()
        assert result == fake

    def test_live_calls_fetch_live(self):
        fake = [{"model": "gemini-2.0-flash", "used_pct": 30.0, "reset_ts": None}]
        with patch("ai_quota.gemini.fetch_live", return_value=fake) as m:
            result = ai_quota.get_usage("gemini", cached=False)
        m.assert_called_once()
        assert result == fake


class TestIsExhausted:
    def test_claude_exhausted_when_session_100(self):
        entries = [{"label": "session", "percent": 100, "reset_ts": None, "cost": ""}]
        with patch("ai_quota.claude.read_cache", return_value=entries):
            assert ai_quota.is_exhausted("claude") is True

    def test_claude_not_exhausted_when_session_below_100(self):
        entries = [{"label": "session", "percent": 80, "reset_ts": None, "cost": ""}]
        with patch("ai_quota.claude.read_cache", return_value=entries):
            assert ai_quota.is_exhausted("claude") is False

    def test_claude_not_exhausted_without_session_label(self):
        # week at 100% doesn't count as exhausted for fallback purposes
        entries = [{"label": "week", "percent": 100, "reset_ts": None, "cost": ""}]
        with patch("ai_quota.claude.read_cache", return_value=entries):
            assert ai_quota.is_exhausted("claude") is False

    def test_gemini_exhausted_when_all_models_at_100(self):
        entries = [
            {"model": "gemini-2.0-flash", "used_pct": 100.0, "reset_ts": None},
            {"model": "gemini-2.0-pro", "used_pct": 100.0, "reset_ts": None},
        ]
        with patch("ai_quota.gemini.read_cache", return_value=entries):
            assert ai_quota.is_exhausted("gemini") is True

    def test_gemini_not_exhausted_when_one_model_available(self):
        entries = [
            {"model": "gemini-2.0-flash", "used_pct": 100.0, "reset_ts": None},
            {"model": "gemini-2.0-pro", "used_pct": 50.0, "reset_ts": None},
        ]
        with patch("ai_quota.gemini.read_cache", return_value=entries):
            assert ai_quota.is_exhausted("gemini") is False

    def test_no_cache_returns_false(self):
        with patch("ai_quota.claude.read_cache", return_value=[]):
            assert ai_quota.is_exhausted("claude") is False

    def test_codex_exhausted(self):
        entries = [{"model": "gpt-5.2-codex", "used_pct": 100.0, "reset_ts": None}]
        with patch("ai_quota.codex.read_cache", return_value=entries):
            assert ai_quota.is_exhausted("codex") is True

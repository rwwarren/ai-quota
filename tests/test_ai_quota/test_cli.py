"""Tests for ai_quota.cli — CLI entrypoint."""
import json
import time
from unittest.mock import patch

import pytest

from ai_quota.cli import main
from ai_quota.providers import claude


class TestMainUsage:
    def test_no_args_exits(self, capsys):
        with pytest.raises(SystemExit):
            main([])

    def test_unknown_provider_exits(self, capsys):
        with pytest.raises(SystemExit):
            main(["openai"])


class TestMainClaude:
    FAKE_ENTRIES = [{"label": "session", "percent": 42, "reset_ts": None, "cost": ""}]

    @patch("ai_quota.providers.claude.fetch_live")
    def test_default_pretty(self, mock_fetch, capsys):
        mock_fetch.return_value = self.FAKE_ENTRIES
        main(["claude"])
        out = capsys.readouterr().out
        assert "42%" in out

    @patch("ai_quota.providers.claude.fetch_live")
    def test_json_output(self, mock_fetch, capsys):
        mock_fetch.return_value = self.FAKE_ENTRIES
        main(["claude", "--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data[0]["percent"] == 42

    @patch("ai_quota.providers.claude.fetch_live")
    def test_short_output(self, mock_fetch, capsys):
        mock_fetch.return_value = self.FAKE_ENTRIES
        main(["claude", "--short"])
        assert "session: 42%" in capsys.readouterr().out

    @patch("ai_quota.providers.claude.fetch_live")
    def test_slack_output(self, mock_fetch, capsys):
        mock_fetch.return_value = self.FAKE_ENTRIES
        main(["claude", "--slack"])
        out = capsys.readouterr().out
        assert "Claude Code Usage" in out

    @patch("ai_quota.providers.claude.read_cache")
    def test_cached_mode(self, mock_cache, capsys):
        mock_cache.return_value = self.FAKE_ENTRIES
        main(["claude", "--cached", "--short"])
        assert "session: 42%" in capsys.readouterr().out

    @patch("ai_quota.providers.claude.read_cache")
    def test_cached_no_data_exits(self, mock_cache, capsys):
        mock_cache.return_value = []
        with pytest.raises(SystemExit):
            main(["claude", "--cached"])

    @patch("ai_quota.providers.claude.write_cache")
    @patch("ai_quota.providers.claude.fetch_live")
    def test_refresh_mode(self, mock_fetch, mock_write, capsys):
        mock_fetch.return_value = self.FAKE_ENTRIES
        main(["claude", "--refresh"])
        mock_write.assert_called_once_with(self.FAKE_ENTRIES)
        assert "session: 42%" in capsys.readouterr().out

    @patch("ai_quota.providers.claude.fetch_live")
    def test_live_no_data_exits(self, mock_fetch, capsys):
        mock_fetch.return_value = []
        with pytest.raises(SystemExit):
            main(["claude", "--pretty"])


class TestMainAll:
    @patch("ai_quota.providers.codex.read_cache", return_value=[])
    @patch("ai_quota.providers.gemini.read_cache", return_value=[])
    @patch("ai_quota.providers.claude.read_cache")
    def test_all_short(self, mock_claude, mock_gemini, mock_codex, capsys):
        mock_claude.return_value = [{"label": "session", "percent": 50, "reset_ts": None, "cost": ""}]
        main(["all"])
        out = capsys.readouterr().out
        assert "session: 50%" in out
        assert "no cached data" in out

    @patch("ai_quota.providers.codex.read_cache", return_value=[])
    @patch("ai_quota.providers.gemini.read_cache", return_value=[])
    @patch("ai_quota.providers.claude.read_cache")
    def test_all_slack(self, mock_claude, mock_gemini, mock_codex, capsys):
        mock_claude.return_value = [{"label": "session", "percent": 50, "reset_ts": None, "cost": ""}]
        main(["all", "--slack"])
        out = capsys.readouterr().out
        assert "Claude Code Usage" in out


class TestCliPrintFallback:
    """_print falls back to fmt_short for unknown format flags."""

    @patch("ai_quota.providers.claude.fetch_live")
    def test_unknown_format_falls_back_to_short(self, mock_fetch, capsys):
        mock_fetch.return_value = [
            {"label": "session", "percent": 42, "reset_ts": None, "cost": ""}
        ]
        main(["claude", "--bogus"])
        out = capsys.readouterr().out
        assert "session: 42%" in out


class TestFetchWithTimeout:
    """_fetch_with_timeout."""

    @patch("ai_quota.providers.claude.fetch_live")
    def test_timeout_returns_empty(self, mock_fetch, capsys):
        def slow():
            time.sleep(5)
            return [{"label": "x"}]

        mock_fetch.side_effect = slow
        from ai_quota.cli import _fetch_with_timeout

        result = _fetch_with_timeout("claude", claude, timeout=0)
        assert result == []


class TestRunAllRefresh:
    """_run_all with --refresh."""

    @patch("ai_quota.cli._fetch_with_timeout")
    def test_refresh_writes_cache_and_prints(self, mock_timeout, capsys):
        def per_provider(name, mod, timeout):
            if name == "claude":
                return [{"label": "session", "percent": 55, "reset_ts": None, "cost": ""}]
            if name == "gemini":
                return [{"model": "flash", "used_pct": 30.0, "reset_ts": None}]
            if name == "codex":
                return [{"model": "codex", "used_pct": 10, "reset_ts": None,
                         "today_tokens": 0, "today_sessions": 0,
                         "all_time_tokens": 0, "all_time_sessions": 0}]
            return []

        mock_timeout.side_effect = per_provider
        with patch("ai_quota.providers.claude.write_cache"), \
             patch("ai_quota.providers.gemini.write_cache"), \
             patch("ai_quota.providers.codex.write_cache"), \
             patch("ai_quota.providers.kilo.write_cache"), \
             patch("ai_quota.providers.lmstudio.write_cache"):
            main(["all", "--refresh"])
        out = capsys.readouterr().out
        assert "claude:" in out

    @patch("ai_quota.cli._fetch_with_timeout")
    def test_refresh_no_data_prints_stderr(self, mock_timeout, capsys):
        mock_timeout.return_value = []
        main(["all", "--refresh"])
        err = capsys.readouterr().err
        assert "no usage data" in err


class TestMainModule:
    """__main__.py and cli.py __name__ guards."""

    def test_run_as_module(self):
        import subprocess
        result = subprocess.run(
            [".venv/bin/python3", "-m", "ai_quota"],
            capture_output=True, text=True,
        )
        assert result.returncode == 1

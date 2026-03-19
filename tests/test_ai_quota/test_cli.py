"""Tests for ai_quota.cli — CLI entrypoint."""
import json
from unittest.mock import patch

import pytest

from ai_quota.cli import main


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

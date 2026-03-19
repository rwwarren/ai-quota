"""Tests for provider-level formatters (fmt_short, fmt_slack, fmt_pretty)."""

from ai_quota.providers import claude, codex, gemini


class TestClaudeFormatters:
    ENTRIES = [
        {"label": "session", "percent": 42, "reset_ts": None, "cost": ""},
        {"label": "week", "percent": 20, "reset_ts": None, "cost": "$1.00 used of $5.00"},
    ]

    def test_fmt_short(self):
        result = claude.fmt_short(self.ENTRIES)
        assert "session: 42%" in result
        assert "week: 20%" in result
        assert "|" in result

    def test_fmt_pretty(self):
        result = claude.fmt_pretty(self.ENTRIES)
        assert "42% used" in result
        assert "$1.00" in result

    def test_fmt_slack(self):
        result = claude.fmt_slack(self.ENTRIES)
        assert "Claude Code Usage" in result
        assert "42" in result


class TestGeminiFormatters:
    ENTRIES = [
        {"model": "gemini-2.0-flash", "used_pct": 25.0, "reset_ts": None},
    ]

    def test_fmt_short(self):
        result = gemini.fmt_short(self.ENTRIES)
        assert "gemini-2.0-flash: 25.0%" in result

    def test_fmt_slack(self):
        result = gemini.fmt_slack(self.ENTRIES)
        assert "Gemini CLI Usage" in result

    def test_fmt_slack_empty(self):
        result = gemini.fmt_slack([])
        assert "No Gemini" in result


class TestCodexFormatters:
    ENTRIES = [{
        "model": "gpt-5.2-codex",
        "used_pct": 7.0,
        "reset_ts": None,
        "today_tokens": 1234,
        "today_sessions": 2,
        "all_time_tokens": 5000,
        "all_time_sessions": 10,
    }]

    def test_fmt_short(self):
        result = codex.fmt_short(self.ENTRIES)
        assert "gpt-5.2-codex: 7%" in result

    def test_fmt_short_none_pct(self):
        entries = [{"model": "codex", "used_pct": None}]
        assert "?" in codex.fmt_short(entries)

    def test_fmt_slack(self):
        result = codex.fmt_slack(self.ENTRIES)
        assert "Codex" in result
        assert "1,234 tokens" in result

    def test_fmt_slack_empty(self):
        result = codex.fmt_slack([])
        assert "No Codex" in result

    def test_fmt_slack_none_pct(self):
        entries = [{
            "model": "codex",
            "used_pct": None,
            "reset_ts": None,
            "today_tokens": 0,
            "today_sessions": 0,
            "all_time_tokens": 0,
            "all_time_sessions": 0,
        }]
        result = codex.fmt_slack(entries)
        assert "unknown" in result

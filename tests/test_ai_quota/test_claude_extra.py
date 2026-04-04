"""Extra tests for claude parsing edge cases."""
from datetime import datetime, timedelta
from unittest.mock import patch

from ai_quota.providers import claude
from ai_quota.providers.claude import (
    _clean,
    _normalize_label,
    _parse_reset_ts,
    fmt_pretty,
    parse_status_bar,
    parse_usage,
)


class TestCleanExtra:
    def test_empty_string(self):
        assert _clean("") == ""

    def test_only_bar_chars_kept_empty(self):
        assert _clean("  ███░░░  ") == "███░░░"


class TestNormalizeLabelExtra:
    def test_addon_variant(self):
        assert _normalize_label("addon usage") == "Extra usage"

    def test_daily(self):
        assert _normalize_label("daily limit") == "daily"

    def test_day(self):
        assert _normalize_label("day usage") == "daily"


class TestParseUsageExtra:
    def test_bar_only_line_not_used_as_label(self):
        lines = [
            "██████████░░░░░░░░░░",
            "session",
            "50% used",
        ]
        entries = parse_usage(lines)
        assert len(entries) == 1
        assert entries[0]["label"] == "session"

    def test_cost_on_reset_line(self):
        lines = [
            "Extra usage",
            "30% used",
            "$1.23 used of $5.00 Resets 11pm (America/Los_Angeles)",
        ]
        entries = parse_usage(lines)
        assert entries[0]["reset_ts"] is not None
        # When $ and reset are on same line, it goes to reset_info
        # cost_info stays empty since the line has both
        assert entries[0]["cost"] == ""

    def test_cost_separate_from_reset(self):
        lines = [
            "Extra usage",
            "30% used",
            "$1.23 used of $5.00",
            "Resets 11pm (America/Los_Angeles)",
        ]
        entries = parse_usage(lines)
        assert "$1.23" in entries[0]["cost"]
        assert entries[0]["reset_ts"] is not None


class TestParseResetTsExtra:
    def test_date_with_minutes(self):
        future = datetime.now() + timedelta(days=10)
        date_str = future.strftime("%b %-d")
        raw = f"Resets {date_str} at 2:30pm (America/Los_Angeles)"
        ts = _parse_reset_ts(raw)
        assert ts is not None
        dt = datetime.fromisoformat(ts)
        assert dt.hour == 14
        assert dt.minute == 30

    def test_am_noon_boundary(self):
        # "12pm" should be hour 12
        ts = _parse_reset_ts("Resets 12pm (America/Los_Angeles)")
        assert ts is not None
        dt = datetime.fromisoformat(ts)
        assert dt.hour == 12

    def test_date_past_rolls_year(self):
        past = datetime.now() - timedelta(days=30)
        date_str = past.strftime("%b %-d")
        raw = f"Resets {date_str} at 10pm (America/Los_Angeles)"
        ts = _parse_reset_ts(raw)
        if ts is not None:
            dt = datetime.fromisoformat(ts)
            assert dt > datetime.now()


class TestParseStatusBar:
    """parse_status_bar."""

    def test_basic_status_bar(self):
        line = "[███░░░░░░░] 34% 3h 59m (3:00 AM) | week: 75% 22h 59m (10:00 PM)"
        entries = parse_status_bar([line])
        assert len(entries) == 2
        assert entries[0]["label"] == "session"
        assert entries[0]["percent"] == 34
        assert entries[1]["label"] == "week"
        assert entries[1]["percent"] == 75

    def test_session_only(self):
        line = "[███░░░] 50% 2h 30m (5:00 PM)"
        entries = parse_status_bar([line])
        assert len(entries) == 1
        assert entries[0]["label"] == "session"
        assert entries[0]["percent"] == 50

    def test_no_match_returns_empty(self):
        assert parse_status_bar(["no bar here"]) == []

    def test_skips_lines_without_percent(self):
        assert parse_status_bar(["hello world", "no percent"]) == []


class TestClaudeReadCacheLastChecked:
    def test_delegates_to_cache(self, tmp_path):
        from ai_quota.cache import write_cache
        cache_file = str(tmp_path / "test.cache")
        write_cache(cache_file, [{"label": "test"}])
        with patch.object(claude, "CACHE_FILE", cache_file):
            result = claude.read_cache_last_checked()
        assert result is not None
        assert isinstance(result, float)


class TestClaudeFmtPrettyReset:
    """fmt_pretty includes reset line."""

    def test_pretty_with_reset(self):
        future = (datetime.now() + timedelta(hours=2)).isoformat()
        entries = [{"label": "session", "percent": 42, "reset_ts": future, "cost": "$1.50"}]
        out = fmt_pretty(entries)
        assert "42% used" in out
        assert "$1.50" in out
        assert "h" in out or "m" in out


class TestClaudeParseUsageBreakOnEmpty:
    """Break when next line after a match is empty."""

    def test_stops_scanning_on_empty_line(self):
        lines = [
            "session",
            "██████░░░░ 60% used",
            "",
        ]
        entries = parse_usage(lines)
        assert len(entries) == 1
        assert entries[0]["percent"] == 60
        assert entries[0]["cost"] == ""


class TestClaudeParseResetTsDateEdges:
    """'am' at hour 12 → hour 0. ValueError in date parse."""

    def test_date_format_am_at_12(self):
        result = _parse_reset_ts("Resets Jan 15 at 12:30 am")
        assert result is not None
        parsed = datetime.fromisoformat(result)
        assert parsed.hour == 0
        assert parsed.minute == 30

    def test_date_format_invalid_month_returns_none(self):
        result = _parse_reset_ts("Resets Xyz 99 at 3 pm")
        assert result is None

"""Tests for ai_quota.providers.claude — pure parsing functions only."""
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

from ai_quota.providers.claude import parse_usage, _parse_reset_ts, _clean, _normalize_label


# ---------------------------------------------------------------------------
# _clean
# ---------------------------------------------------------------------------

class TestClean:
    def test_collapses_whitespace(self):
        assert _clean("  foo   bar  ") == "foo bar"

    def test_drops_isolated_single_chars(self):
        # pyte garbles "session" into "session t f l e"
        result = _clean("session t f l e")
        assert result == "session"

    def test_fixes_resets_garbling(self):
        assert "Resets" in _clean("Rese ts 11pm")
        assert "Resets" in _clean("Re sets 11pm")


# ---------------------------------------------------------------------------
# _normalize_label
# ---------------------------------------------------------------------------

class TestNormalizeLabel:
    def test_session(self):
        assert _normalize_label("session usage") == "session"
        assert _normalize_label("Session") == "session"

    def test_week(self):
        assert _normalize_label("weekly limit") == "week"

    def test_extra(self):
        assert _normalize_label("Extra add-on usage") == "Extra usage"

    def test_passthrough(self):
        assert _normalize_label("foobar") == "foobar"


# ---------------------------------------------------------------------------
# parse_usage
# ---------------------------------------------------------------------------

class TestParseUsage:
    def test_single_entry(self):
        lines = [
            "  session",
            "  80% used",
            "  Resets 11pm (America/Los_Angeles)",
        ]
        entries = parse_usage(lines)
        assert len(entries) == 1
        assert entries[0]["label"] == "session"
        assert entries[0]["percent"] == 80

    def test_multiple_entries(self):
        lines = [
            "session",
            "75% used",
            "Resets 11pm (America/Los_Angeles)",
            "week",
            "40% used",
        ]
        entries = parse_usage(lines)
        assert len(entries) == 2
        assert entries[0]["percent"] == 75
        assert entries[1]["percent"] == 40

    def test_no_match_returns_empty(self):
        assert parse_usage(["nothing here", "no usage"]) == []

    def test_100_percent(self):
        entries = parse_usage(["session", "100% used"])
        assert entries[0]["percent"] == 100

    def test_cost_extracted(self):
        lines = [
            "Extra usage",
            "30% used",
            "$1.23 used of $5.00",
        ]
        entries = parse_usage(lines)
        assert "$1.23" in entries[0]["cost"]

    def test_reset_ts_populated(self):
        lines = ["session", "50% used", "Resets 11pm (America/Los_Angeles)"]
        entries = parse_usage(lines)
        assert entries[0]["reset_ts"] is not None

    def test_reset_ts_none_when_absent(self):
        lines = ["session", "50% used"]
        entries = parse_usage(lines)
        assert entries[0]["reset_ts"] is None


# ---------------------------------------------------------------------------
# _parse_reset_ts
# ---------------------------------------------------------------------------

class TestParseResetTs:
    def _future_ts(self, raw: str) -> str:
        result = _parse_reset_ts(raw)
        assert result is not None, f"Expected a timestamp from {raw!r}"
        return result

    def test_time_only_pm(self):
        ts = self._future_ts("Resets 11pm (America/Los_Angeles)")
        dt = datetime.fromisoformat(ts)
        assert dt > datetime.now()
        assert dt.hour == 23

    def test_time_only_am(self):
        ts = self._future_ts("Resets 6am (America/Los_Angeles)")
        dt = datetime.fromisoformat(ts)
        assert dt.hour == 6

    def test_time_midnight(self):
        ts = self._future_ts("Resets 12am (America/Los_Angeles)")
        dt = datetime.fromisoformat(ts)
        assert dt.hour == 0

    def test_time_noon(self):
        ts = self._future_ts("Resets 12pm (America/Los_Angeles)")
        dt = datetime.fromisoformat(ts)
        assert dt.hour == 12

    def test_time_with_minutes(self):
        ts = self._future_ts("Resets 2:30pm (America/Los_Angeles)")
        dt = datetime.fromisoformat(ts)
        assert dt.hour == 14
        assert dt.minute == 30

    def test_date_format(self):
        # Use a date well in the future to avoid year-rollover edge case
        future = datetime.now() + timedelta(days=10)
        date_str = future.strftime("%b %-d")
        raw = f"Resets {date_str} at 10pm (America/Los_Angeles)"
        ts = self._future_ts(raw)
        dt = datetime.fromisoformat(ts)
        assert dt.hour == 22

    def test_empty_returns_none(self):
        assert _parse_reset_ts("") is None

    def test_no_resets_keyword_returns_none(self):
        assert _parse_reset_ts("11pm (America/Los_Angeles)") is None

    def test_cost_line_with_resets(self):
        ts = self._future_ts("$1.23 used of $5.00 Resets 11pm (America/Los_Angeles)")
        assert ts is not None

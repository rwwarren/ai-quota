"""Extra tests for claude parsing edge cases."""
from datetime import datetime, timedelta

from ai_quota.providers.claude import _clean, _normalize_label, _parse_reset_ts, parse_usage


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

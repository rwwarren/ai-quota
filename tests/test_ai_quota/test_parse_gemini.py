"""Tests for ai_quota.providers.gemini — pure parsing functions only."""
from datetime import datetime, timedelta

import pytest

from ai_quota.providers.gemini import _parse_reset_ts, parse_usage

# ---------------------------------------------------------------------------
# parse_usage
# ---------------------------------------------------------------------------

class TestParseUsage:
    def test_basic_entry(self):
        raw = "gemini-2.0-flash  1000  75.0%  resets in 3h 24m"
        entries = parse_usage(raw)
        assert len(entries) == 1
        assert entries[0]["model"] == "gemini-2.0-flash"
        assert entries[0]["used_pct"] == pytest.approx(75.0)

    def test_skips_header_words(self):
        raw = "model  1000  75%\ngemini-2.0-pro  500  60%"
        entries = parse_usage(raw)
        assert all(e["model"] != "model" for e in entries)

    def test_box_drawing_stripped(self):
        raw = "│gemini-2.0-flash│ 1000 │ 50.0% │"
        entries = parse_usage(raw)
        assert len(entries) == 1
        assert entries[0]["used_pct"] == pytest.approx(50.0)  # 50% used is 50% either way

    def test_empty_raw_returns_empty(self):
        assert parse_usage("") == []

    def test_reset_ts_extracted(self):
        raw = "gemini-2.0-flash  1000  80%  resets in 1h 30m"
        entries = parse_usage(raw)
        assert entries[0]["reset_ts"] is not None

    def test_reset_ts_none_when_unknown(self):
        raw = "gemini-2.0-flash  1000  80%"
        entries = parse_usage(raw)
        assert entries[0]["reset_ts"] is None

    def test_multiple_models(self):
        raw = "gemini-2.0-flash  1000  75%\ngemini-2.0-pro  500  40%"
        entries = parse_usage(raw)
        assert len(entries) == 2

    def test_bar_with_black_rectangle_chars(self):
        raw = "gemini-2.5-flash           -    ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬    2%  10:10 PM (2h 56m)"
        entries = parse_usage(raw)
        assert len(entries) == 1
        assert entries[0]["model"] == "gemini-2.5-flash"
        assert entries[0]["used_pct"] == pytest.approx(2.0)

    def test_new_reset_format_time_with_duration(self):
        raw = "gemini-2.5-flash  -  ▬▬▬▬  2%  10:10 PM (2h 56m)"
        entries = parse_usage(raw)
        assert len(entries) == 1
        assert entries[0]["reset_ts"] is not None
        dt = datetime.fromisoformat(entries[0]["reset_ts"])
        expected = datetime.now() + timedelta(hours=2, minutes=56)
        assert abs((dt - expected).total_seconds()) < 5

    def test_new_reset_format_24h(self):
        raw = "gemini-2.5-pro  -  ▬▬▬▬  0%  7:15 PM (24h)"
        entries = parse_usage(raw)
        assert len(entries) == 1
        assert entries[0]["reset_ts"] is not None
        dt = datetime.fromisoformat(entries[0]["reset_ts"])
        expected = datetime.now() + timedelta(hours=24)
        assert abs((dt - expected).total_seconds()) < 5


# ---------------------------------------------------------------------------
# _parse_reset_ts
# ---------------------------------------------------------------------------

class TestParseResetTs:
    def test_hours_and_minutes(self):
        ts = _parse_reset_ts("resets in 3h 24m")
        assert ts is not None
        dt = datetime.fromisoformat(ts)
        expected = datetime.now() + timedelta(hours=3, minutes=24)
        assert abs((dt - expected).total_seconds()) < 5

    def test_days(self):
        ts = _parse_reset_ts("resets in 3 days")
        assert ts is not None
        dt = datetime.fromisoformat(ts)
        expected = datetime.now() + timedelta(days=3)
        assert abs((dt - expected).total_seconds()) < 5

    def test_days_hours_minutes(self):
        ts = _parse_reset_ts("resets in 1d 2h 30m")
        assert ts is not None
        dt = datetime.fromisoformat(ts)
        expected = datetime.now() + timedelta(days=1, hours=2, minutes=30)
        assert abs((dt - expected).total_seconds()) < 5

    def test_unknown_returns_none(self):
        assert _parse_reset_ts("Unknown") is None

    def test_empty_returns_none(self):
        assert _parse_reset_ts("") is None

    def test_no_match_returns_none(self):
        assert _parse_reset_ts("some other string") is None

    def test_zero_minutes_returns_none(self):
        assert _parse_reset_ts("resets in 0m") is None

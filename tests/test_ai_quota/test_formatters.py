"""Tests for ai_quota.formatters — shared formatting helpers."""
from datetime import datetime, timedelta

from ai_quota.formatters import fmt_bar, fmt_reset


class TestFmtReset:
    def test_empty_returns_empty(self):
        assert fmt_reset("") == ""
        assert fmt_reset(None) == ""

    def test_invalid_ts_returns_empty(self):
        assert fmt_reset("not-a-timestamp") == ""

    def test_future_hours(self):
        target = datetime.now() + timedelta(hours=2, minutes=30)
        result = fmt_reset(target.isoformat())
        assert "resets in 2h" in result
        assert "m" in result  # minutes present

    def test_future_minutes_only(self):
        target = datetime.now() + timedelta(minutes=15)
        result = fmt_reset(target.isoformat())
        assert "resets in 1" in result or "resets in 15m" in result

    def test_future_days(self):
        target = datetime.now() + timedelta(days=2, hours=3)
        result = fmt_reset(target.isoformat())
        assert "2d" in result

    def test_past_shows_zero(self):
        target = datetime.now() - timedelta(hours=1)
        result = fmt_reset(target.isoformat())
        assert "resets in 0m" in result


class TestFmtBar:
    def test_zero_percent(self):
        bar, emoji = fmt_bar(0)
        assert "░" in bar
        assert emoji == ":large_green_circle:"

    def test_50_percent(self):
        bar, emoji = fmt_bar(50)
        assert "█" in bar
        assert emoji == ":large_yellow_circle:"

    def test_80_percent(self):
        bar, emoji = fmt_bar(80)
        assert emoji == ":red_circle:"

    def test_100_percent(self):
        bar, emoji = fmt_bar(100)
        assert bar.count("█") == 20
        assert bar.count("░") == 0

    def test_custom_width(self):
        bar, _ = fmt_bar(50, width=10)
        assert len(bar) == 10

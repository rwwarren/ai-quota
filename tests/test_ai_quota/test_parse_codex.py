"""Tests for ai_quota.providers.codex — pure parsing functions only."""
from datetime import datetime, timedelta

from ai_quota.providers.codex import _parse_reset_ts, parse_tui_output

# ---------------------------------------------------------------------------
# parse_tui_output
# ---------------------------------------------------------------------------

class TestParseTuiOutput:
    def test_status_panel_full(self):
        text = (
            "Model: gpt-5.2-codex (reasoning medium)\n"
            "Account: user@example.com │\n"
            "Weekly limit: [████████░░] 93% left (resets 14:39 on 21 Mar)\n"
        )
        info = parse_tui_output(text)
        assert info["model"] == "gpt-5.2-codex"
        assert info["reasoning_effort"] == "medium"
        assert info["percent_left"] == 93
        assert info["resets_time"] == "14:39"
        assert info["resets_date"] == "21 Mar"
        assert info["account"] == "user@example.com"

    def test_status_bar_fallback(self):
        text = "gpt-5.2-codex medium · 75% left · ~/myproject"
        info = parse_tui_output(text)
        assert info["model"] == "gpt-5.2-codex"
        assert info["percent_left"] == 75

    def test_status_panel_takes_priority_over_bar(self):
        text = (
            "Weekly limit: [████████░░] 93% left (resets 14:39 on 21 Mar)\n"
            "gpt-5.2-codex medium · 50% left · ~/myproject\n"
        )
        info = parse_tui_output(text)
        assert info["percent_left"] == 93

    def test_empty_text_returns_empty_dict(self):
        assert parse_tui_output("") == {}

    def test_no_percent_left(self):
        text = "Model: gpt-5.2-codex (reasoning medium)\n"
        info = parse_tui_output(text)
        assert "percent_left" not in info
        assert info["model"] == "gpt-5.2-codex"

    def test_100_percent_left(self):
        text = "Weekly limit: [░░░░░░░░░░] 100% left (resets 14:39 on 21 Mar)\n"
        info = parse_tui_output(text)
        assert info["percent_left"] == 100

    def test_0_percent_left(self):
        text = "Weekly limit: [██████████] 0% left (resets 14:39 on 21 Mar)\n"
        info = parse_tui_output(text)
        assert info["percent_left"] == 0


# ---------------------------------------------------------------------------
# _parse_reset_ts
# ---------------------------------------------------------------------------

class TestParseResetTs:
    def test_valid(self):
        # Use a date 10 days ahead to avoid year-rollover edge case
        future = datetime.now() + timedelta(days=10)
        resets_date = future.strftime("%-d %b")
        ts = _parse_reset_ts("14:39", resets_date)
        assert ts is not None
        dt = datetime.fromisoformat(ts)
        assert dt.hour == 14
        assert dt.minute == 39

    def test_empty_time_returns_none(self):
        assert _parse_reset_ts("", "21 Mar") is None

    def test_invalid_date_returns_none(self):
        assert _parse_reset_ts("14:39", "32 Foo") is None

    def test_past_date_rolls_to_next_year(self):
        # Use a past date
        past = datetime.now() - timedelta(days=10)
        resets_date = past.strftime("%-d %b")
        ts = _parse_reset_ts("00:00", resets_date)
        assert ts is not None
        dt = datetime.fromisoformat(ts)
        assert dt > datetime.now()

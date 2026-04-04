"""Tests for ai_quota.providers.codex — pure parsing functions only."""
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch

from ai_quota.providers import codex
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


# ---------------------------------------------------------------------------
# _query_db
# ---------------------------------------------------------------------------

class TestCodexQueryDb:
    """_query_db success path."""

    def test_query_db_with_data(self, tmp_path):
        db_path = tmp_path / "state.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE threads (tokens_used INTEGER, created_at INTEGER)")
        now_ts = int(datetime.now().timestamp())
        conn.execute("INSERT INTO threads VALUES (100, ?)", (now_ts,))
        conn.execute("INSERT INTO threads VALUES (200, ?)", (now_ts + 10,))
        conn.commit()
        conn.close()

        with patch.object(codex, "CODEX_STATE_DB", str(db_path)):
            result = codex._query_db()
        assert result is not None
        assert result["today_tokens"] == 300
        assert result["today_sessions"] == 2
        assert result["all_time_tokens"] == 300
        assert result["all_time_sessions"] == 2


class TestCodexQueryDbException:
    """Exception in _query_db returns None."""

    def test_corrupt_db_returns_none(self, tmp_path):
        db_path = tmp_path / "state.sqlite"
        db_path.write_text("not a database")
        with patch.object(codex, "CODEX_STATE_DB", str(db_path)):
            result = codex._query_db()
        assert result is None


class TestCodexReadCacheLastChecked:
    def test_delegates_to_cache(self, tmp_path):
        from ai_quota.cache import write_cache
        cache_file = str(tmp_path / "test.cache")
        write_cache(cache_file, [{"model": "codex"}])
        with patch.object(codex, "CACHE_FILE", cache_file):
            result = codex.read_cache_last_checked()
        assert isinstance(result, float)


class TestCodexFmtSlackResetLine:
    """fmt_slack includes reset line when reset_ts is set."""

    def test_slack_with_reset(self):
        future = (datetime.now() + timedelta(hours=3)).isoformat()
        entries = [{
            "model": "codex",
            "used_pct": 45,
            "reset_ts": future,
            "today_tokens": 500,
            "today_sessions": 2,
            "all_time_tokens": 1000,
            "all_time_sessions": 5,
        }]
        out = codex.fmt_slack(entries)
        assert "Codex" in out
        assert "_" in out

    def test_slack_with_none_pct_shows_unknown(self):
        entries = [{
            "model": "codex",
            "used_pct": None,
            "reset_ts": None,
            "today_tokens": 0,
            "today_sessions": 0,
            "all_time_tokens": 0,
            "all_time_sessions": 0,
        }]
        out = codex.fmt_slack(entries)
        assert "unknown" in out

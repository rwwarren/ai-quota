"""Extra tests for gemini parsing edge cases and cache/formatters."""
from datetime import datetime, timedelta
from unittest.mock import patch

from ai_quota.providers import gemini
from ai_quota.providers.gemini import _parse_reset_ts, parse_usage


class TestParseUsageEdgeCases:
    def test_value_error_in_float_skipped(self):
        # A line where the "percentage" isn't a valid float shouldn't crash
        raw = "gemini-2.0-flash  1000  abc%"
        entries = parse_usage(raw)
        assert entries == []

    def test_model_named_total_skipped(self):
        raw = "total  5000  90%"
        entries = parse_usage(raw)
        assert entries == []

    def test_model_named_reqs_skipped(self):
        raw = "reqs  100  50%"
        entries = parse_usage(raw)
        assert entries == []

    def test_model_named_usage_skipped(self):
        raw = "usage  100  50%"
        entries = parse_usage(raw)
        assert entries == []

    def test_no_reset_match_gives_unknown(self):
        raw = "gemini-2.5-pro  1000  80%  some other text"
        entries = parse_usage(raw)
        assert len(entries) == 1
        # "Unknown" is the default when no "resets in" match
        assert entries[0]["reset_ts"] is None


class TestParseResetTsEdgeCases:
    def test_minutes_only(self):
        ts = _parse_reset_ts("resets in 45m")
        assert ts is not None
        dt = datetime.fromisoformat(ts)
        expected = datetime.now() + timedelta(minutes=45)
        assert abs((dt - expected).total_seconds()) < 5

    def test_hours_only(self):
        ts = _parse_reset_ts("resets in 5h")
        assert ts is not None
        dt = datetime.fromisoformat(ts)
        expected = datetime.now() + timedelta(hours=5)
        assert abs((dt - expected).total_seconds()) < 5


class TestGeminiReadCacheLastChecked:
    def test_delegates_to_cache(self, tmp_path):
        from ai_quota.cache import write_cache
        cache_file = str(tmp_path / "test.cache")
        write_cache(cache_file, [{"model": "flash"}])
        with patch.object(gemini, "CACHE_FILE", cache_file):
            result = gemini.read_cache_last_checked()
        assert isinstance(result, float)


class TestGeminiFmtSlackReset:
    """fmt_slack includes reset when present."""

    def test_slack_with_reset(self):
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        entries = [{"model": "gemini-2.0-flash", "used_pct": 80.0, "reset_ts": future}]
        out = gemini.fmt_slack(entries)
        assert "Gemini" in out
        assert "_" in out


class TestGeminiParseUsageValueError:
    """Non-numeric percent in parse_usage is skipped."""

    def test_non_numeric_percent_skipped(self):
        raw = "model-x   abc/100 reqs"
        entries = parse_usage(raw)
        assert entries == []

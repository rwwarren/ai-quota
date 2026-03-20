"""Tests for ai_quota.providers.groq — pure parsing functions only."""
from datetime import datetime, timedelta

import pytest

from ai_quota.providers.groq import parse_rate_limit_headers, parse_reset_duration


# ---------------------------------------------------------------------------
# parse_reset_duration
# ---------------------------------------------------------------------------

class TestParseResetDuration:
    def test_seconds_only(self):
        ts = parse_reset_duration("59.814s")
        assert ts is not None
        dt = datetime.fromisoformat(ts)
        expected = datetime.now() + timedelta(seconds=59.814)
        assert abs((dt - expected).total_seconds()) < 2

    def test_minutes_only(self):
        ts = parse_reset_duration("2m")
        assert ts is not None
        dt = datetime.fromisoformat(ts)
        expected = datetime.now() + timedelta(minutes=2)
        assert abs((dt - expected).total_seconds()) < 2

    def test_minutes_and_seconds(self):
        ts = parse_reset_duration("1m30s")
        assert ts is not None
        dt = datetime.fromisoformat(ts)
        expected = datetime.now() + timedelta(minutes=1, seconds=30)
        assert abs((dt - expected).total_seconds()) < 2

    def test_empty_returns_none(self):
        assert parse_reset_duration("") is None

    def test_zero_returns_none(self):
        assert parse_reset_duration("0s") is None

    def test_unrecognised_returns_none(self):
        assert parse_reset_duration("unknown") is None

    def test_whitespace_stripped(self):
        ts = parse_reset_duration("  30s  ")
        assert ts is not None


# ---------------------------------------------------------------------------
# parse_rate_limit_headers
# ---------------------------------------------------------------------------

class TestParseRateLimitHeaders:
    def _headers(self, *, limit_tokens=1000, remaining_tokens=400,
                 reset_tokens="59s", limit_requests=100, remaining_requests=90,
                 reset_requests="30s"):
        return {
            "x-ratelimit-limit-tokens": str(limit_tokens),
            "x-ratelimit-remaining-tokens": str(remaining_tokens),
            "x-ratelimit-reset-tokens": reset_tokens,
            "x-ratelimit-limit-requests": str(limit_requests),
            "x-ratelimit-remaining-requests": str(remaining_requests),
            "x-ratelimit-reset-requests": reset_requests,
        }

    def test_returns_two_entries(self):
        entries = parse_rate_limit_headers(self._headers())
        assert len(entries) == 2

    def test_token_entry_label(self):
        entries = parse_rate_limit_headers(self._headers())
        labels = [e["model"] for e in entries]
        assert "tokens/min" in labels

    def test_request_entry_label(self):
        entries = parse_rate_limit_headers(self._headers())
        labels = [e["model"] for e in entries]
        assert "requests/min" in labels

    def test_token_used_pct(self):
        # limit=1000, remaining=400 → used=600 → 60%
        entries = parse_rate_limit_headers(self._headers(limit_tokens=1000, remaining_tokens=400))
        token_entry = next(e for e in entries if e["model"] == "tokens/min")
        assert token_entry["used_pct"] == pytest.approx(60.0)

    def test_request_used_pct(self):
        # limit=100, remaining=90 → used=10 → 10%
        entries = parse_rate_limit_headers(self._headers(limit_requests=100, remaining_requests=90))
        req_entry = next(e for e in entries if e["model"] == "requests/min")
        assert req_entry["used_pct"] == pytest.approx(10.0)

    def test_zero_used_when_full_remaining(self):
        entries = parse_rate_limit_headers(
            self._headers(limit_tokens=1000, remaining_tokens=1000)
        )
        token_entry = next(e for e in entries if e["model"] == "tokens/min")
        assert token_entry["used_pct"] == pytest.approx(0.0)

    def test_100_pct_when_exhausted(self):
        entries = parse_rate_limit_headers(
            self._headers(limit_tokens=500, remaining_tokens=0)
        )
        token_entry = next(e for e in entries if e["model"] == "tokens/min")
        assert token_entry["used_pct"] == pytest.approx(100.0)

    def test_reset_ts_populated(self):
        entries = parse_rate_limit_headers(self._headers(reset_tokens="30s"))
        token_entry = next(e for e in entries if e["model"] == "tokens/min")
        assert token_entry["reset_ts"] is not None

    def test_missing_token_headers_skipped(self):
        headers = {
            "x-ratelimit-limit-requests": "100",
            "x-ratelimit-remaining-requests": "50",
            "x-ratelimit-reset-requests": "30s",
        }
        entries = parse_rate_limit_headers(headers)
        assert len(entries) == 1
        assert entries[0]["model"] == "requests/min"

    def test_empty_headers_returns_empty(self):
        assert parse_rate_limit_headers({}) == []

    def test_limit_and_remaining_stored(self):
        entries = parse_rate_limit_headers(
            self._headers(limit_tokens=2000, remaining_tokens=1500)
        )
        token_entry = next(e for e in entries if e["model"] == "tokens/min")
        assert token_entry["limit"] == 2000
        assert token_entry["remaining"] == 1500

    def test_case_insensitive_not_required(self):
        # headers dict is passed in pre-lowercased (as fetch_live does)
        headers = self._headers()
        # All keys already lowercase — just verify normal parsing works
        entries = parse_rate_limit_headers(headers)
        assert len(entries) == 2

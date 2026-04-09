from unittest.mock import patch

from ai_quota.providers import opencode
from ai_quota.providers.opencode import parse_usage


def test_parse_usage_full():
    raw = """
┌────────────────────────────────────────────────────────┐
│                       OVERVIEW                         │
├────────────────────────────────────────────────────────┤
│Sessions                                             12 │
│Messages                                             45 │
│Days                                                  3 │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│                    COST & TOKENS                       │
├────────────────────────────────────────────────────────┤
│Total Cost                                        $1.23 │
│Avg Cost/Day                                      $0.41 │
│Avg Tokens/Session                                20.5K │
│Median Tokens/Session                              8.3K │
│Input                                            500.0K │
│Output                                            25.0K │
│Cache Read                                        100.0 │
│Cache Write                                        50.0 │
└────────────────────────────────────────────────────────┘
"""
    entries = parse_usage(raw)
    assert len(entries) == 1
    e = entries[0]
    assert e["sessions"] == 12
    assert e["messages"] == 45
    assert e["days"] == 3
    assert e["total_cost"] == "$1.23"
    assert e["avg_cost_day"] == "$0.41"
    assert e["avg_tokens_session"] == "20.5K"
    assert e["median_tokens_session"] == "8.3K"
    assert e["input_tokens"] == "500.0K"
    assert e["output_tokens"] == "25.0K"
    assert e["cache_read"] == "100.0"
    assert e["cache_write"] == "50.0"


def test_parse_usage_empty():
    assert parse_usage("") == []
    assert parse_usage("nothing here") == []


def test_parse_usage_partial():
    raw = "Total Cost $2.50 Sessions 8 Input 30K"
    entries = parse_usage(raw)
    assert len(entries) == 1
    e = entries[0]
    assert e["total_cost"] == "$2.50"
    assert e["sessions"] == 8
    assert e["input_tokens"] == "30K"


class TestOpencodeCacheHelpers:
    def test_read_cache_last_checked(self, tmp_path):
        from ai_quota.cache import write_cache
        cache_file = str(tmp_path / "opencode.cache")
        write_cache(cache_file, [{"sessions": 5}])
        with patch.object(opencode, "CACHE_FILE", cache_file):
            result = opencode.read_cache_last_checked()
        assert isinstance(result, float)

    def test_write_cache(self, tmp_path):
        cache_file = str(tmp_path / "opencode.cache")
        with patch.object(opencode, "CACHE_FILE", cache_file):
            opencode.write_cache([{"sessions": 3}])
            data = opencode.read_cache()
        assert data == [{"sessions": 3}]


class TestOpencodeFmtShort:
    def test_empty(self):
        assert opencode.fmt_short([]) == "opencode: no data"

    def test_with_data(self):
        entries = [{"total_cost": "$1.50", "input_tokens": "10K", "output_tokens": "5K"}]
        out = opencode.fmt_short(entries)
        assert "$1.50" in out
        assert "10K" in out
        assert "5K" in out


class TestOpencodeFmtSlack:
    def test_empty(self):
        assert "No OpenCode usage" in opencode.fmt_slack([])

    def test_with_data(self):
        entries = [{
            "total_cost": "$2.00",
            "input_tokens": "15K",
            "output_tokens": "8K",
            "sessions": 3,
            "messages": 10,
        }]
        out = opencode.fmt_slack(entries)
        assert "OpenCode Usage" in out
        assert "$2.00" in out
        assert "3 Sessions" in out

    def test_with_cache_tokens(self):
        entries = [{
            "total_cost": "$0.50",
            "input_tokens": "5K",
            "output_tokens": "2K",
            "sessions": 1,
            "messages": 2,
            "cache_read": "100",
            "cache_write": "50",
        }]
        out = opencode.fmt_slack(entries)
        assert "Cache" in out
        assert "100 Read" in out

    def test_without_cache_tokens(self):
        entries = [{"total_cost": "$0.50", "sessions": 1, "messages": 2}]
        out = opencode.fmt_slack(entries)
        assert "Cache" not in out

from unittest.mock import patch

from ai_quota.providers import kilo
from ai_quota.providers.kilo import parse_usage


def test_parse_usage_full():
    raw = """
┌────────────────────────────────────────────────────────┐
│                       OVERVIEW                         │
├────────────────────────────────────────────────────────┤
│Sessions                                             27 │
│Messages                                             91 │
│Days                                                  1 │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│                    COST & TOKENS                       │
├────────────────────────────────────────────────────────┤
│Total Cost                                        $0.05 │
│Avg Cost/Day                                      $0.01 │
│Avg Tokens/Session                                40.7K │
│Median Tokens/Session                             12.7K │
│Input                                              1.1M │
│Output                                            11.5K │
│Cache Read                                            0 │
│Cache Write                                           0 │
└────────────────────────────────────────────────────────┘


┌────────────────────────────────────────────────────────┐
│                      TOOL USAGE                        │
├────────────────────────────────────────────────────────┤
│ bash               ████████████████████  13 (34.2%)    │
│ glob               █████████████          9 (23.7%)    │
│ read               █████████████          9 (23.7%)    │
│ webfetch           █████████              6 (15.8%)    │
│ question           █                      1 ( 2.6%)    │
└────────────────────────────────────────────────────────┘
"""
    entries = parse_usage(raw)
    assert len(entries) == 1
    e = entries[0]
    assert e["sessions"] == 27
    assert e["messages"] == 91
    assert e["days"] == 1
    assert e["total_cost"] == "$0.05"
    assert e["avg_cost_day"] == "$0.01"
    assert e["input_tokens"] == "1.1M"
    assert e["output_tokens"] == "11.5K"
    assert len(e["tools"]) == 5
    assert e["tools"][0]["tool"] == "bash"
    assert e["tools"][0]["percent"] == 34.2

def test_parse_usage_empty():
    assert parse_usage("") == []
    assert parse_usage("nothing here") == []

def test_parse_usage_partial():
    raw = "Total Cost $1.23 Sessions 5 Input 10K"
    entries = parse_usage(raw)
    assert len(entries) == 1
    e = entries[0]
    assert e["total_cost"] == "$1.23"
    assert e["sessions"] == 5
    assert e["input_tokens"] == "10K"
    assert "tools" not in e


class TestKiloCacheHelpers:
    def test_read_cache_last_checked(self, tmp_path):
        from ai_quota.cache import write_cache
        cache_file = str(tmp_path / "kilo.cache")
        write_cache(cache_file, [{"sessions": 5}])
        with patch.object(kilo, "CACHE_FILE", cache_file):
            result = kilo.read_cache_last_checked()
        assert isinstance(result, float)

    def test_write_cache(self, tmp_path):
        cache_file = str(tmp_path / "kilo.cache")
        with patch.object(kilo, "CACHE_FILE", cache_file):
            kilo.write_cache([{"sessions": 3}])
            data = kilo.read_cache()
        assert data == [{"sessions": 3}]


class TestKiloFmtShort:
    def test_empty(self):
        assert kilo.fmt_short([]) == "kilo: no data"

    def test_with_data(self):
        entries = [{"total_cost": "$1.50", "input_tokens": "10K", "output_tokens": "5K"}]
        out = kilo.fmt_short(entries)
        assert "$1.50" in out
        assert "10K" in out


class TestKiloFmtSlack:
    def test_empty(self):
        assert "No Kilo usage" in kilo.fmt_slack([])

    def test_with_tools(self):
        entries = [{
            "total_cost": "$2.00",
            "input_tokens": "15K",
            "output_tokens": "8K",
            "sessions": 3,
            "messages": 10,
            "tools": [
                {"tool": "bash", "percent": 34.2},
                {"tool": "read", "percent": 20.0},
            ],
        }]
        out = kilo.fmt_slack(entries)
        assert "Kilo Usage" in out
        assert "bash" in out
        assert "Top Tools" in out

    def test_without_tools(self):
        entries = [{"total_cost": "$0.50", "sessions": 1, "messages": 2}]
        out = kilo.fmt_slack(entries)
        assert "Top Tools" not in out

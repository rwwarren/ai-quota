"""Tests for provider-level cache wrappers and fetch_live assembly (codex)."""
import json
from unittest.mock import patch

from ai_quota.providers import claude, codex, gemini


class TestClaudeCache:
    def test_read_cache(self, tmp_path):
        path = str(tmp_path / "cc.cache")
        with open(path, "w") as f:
            json.dump({"updated": 1, "entries": [{"label": "session", "percent": 10}]}, f)
        with patch.object(claude, "CACHE_FILE", path):
            assert claude.read_cache() == [{"label": "session", "percent": 10}]

    def test_write_cache(self, tmp_path):
        path = str(tmp_path / "cc.cache")
        with patch.object(claude, "CACHE_FILE", path):
            claude.write_cache([{"a": 1}])
        with open(path) as f:
            data = json.load(f)
        assert data["entries"] == [{"a": 1}]


class TestGeminiCache:
    def test_read_cache(self, tmp_path):
        path = str(tmp_path / "gem.cache")
        with open(path, "w") as f:
            json.dump({"updated": 1, "entries": [{"model": "flash"}]}, f)
        with patch.object(gemini, "CACHE_FILE", path):
            assert gemini.read_cache() == [{"model": "flash"}]

    def test_write_cache(self, tmp_path):
        path = str(tmp_path / "gem.cache")
        with patch.object(gemini, "CACHE_FILE", path):
            gemini.write_cache([{"b": 2}])
        with open(path) as f:
            assert json.load(f)["entries"] == [{"b": 2}]


class TestCodexCache:
    def test_read_cache(self, tmp_path):
        path = str(tmp_path / "codex.cache")
        with open(path, "w") as f:
            json.dump({"updated": 1, "entries": [{"model": "codex"}]}, f)
        with patch.object(codex, "CACHE_FILE", path):
            assert codex.read_cache() == [{"model": "codex"}]

    def test_write_cache(self, tmp_path):
        path = str(tmp_path / "codex.cache")
        with patch.object(codex, "CACHE_FILE", path):
            codex.write_cache([{"c": 3}])
        with open(path) as f:
            assert json.load(f)["entries"] == [{"c": 3}]


class TestCodexFetchLive:
    @patch("ai_quota.providers.codex._query_db")
    @patch("ai_quota.providers.codex.fetch_quota")
    def test_combines_tui_and_db(self, mock_quota, mock_db):
        mock_quota.return_value = {
            "model": "gpt-5.2-codex",
            "percent_left": 90,
            "resets_time": "",
            "resets_date": "",
        }
        mock_db.return_value = {
            "today_tokens": 100,
            "today_sessions": 1,
            "all_time_tokens": 500,
            "all_time_sessions": 5,
        }
        entries = codex.fetch_live()
        assert len(entries) == 1
        assert entries[0]["model"] == "gpt-5.2-codex"
        assert entries[0]["used_pct"] == 10
        assert entries[0]["today_tokens"] == 100

    @patch("ai_quota.providers.codex._query_db", return_value=None)
    @patch("ai_quota.providers.codex.fetch_quota", return_value=None)
    def test_both_none_returns_empty(self, mock_quota, mock_db):
        assert codex.fetch_live() == []

    @patch("ai_quota.providers.codex._query_db", return_value=None)
    @patch("ai_quota.providers.codex.fetch_quota")
    def test_no_db_still_works(self, mock_quota, mock_db):
        mock_quota.return_value = {"model": "codex", "percent_left": 50}
        entries = codex.fetch_live()
        assert len(entries) == 1
        assert entries[0]["used_pct"] == 50
        assert entries[0]["today_tokens"] == 0


class TestCodexFetchQuota:
    @patch("ai_quota.providers.codex._spawn_codex_and_read", side_effect=Exception("no codex"))
    def test_exception_returns_none(self, mock_spawn):
        assert codex.fetch_quota() is None

    @patch("ai_quota.providers.codex._spawn_codex_and_read", return_value="nothing useful")
    def test_empty_parse_returns_none(self, mock_spawn):
        assert codex.fetch_quota() is None

    @patch("ai_quota.providers.codex._spawn_codex_and_read")
    def test_valid_parse(self, mock_spawn):
        mock_spawn.return_value = (
            "Model: gpt-5.2-codex (reasoning medium)\n"
            "Weekly limit: [████░░░░░░] 60% left (resets 14:39 on 21 Mar)\n"
        )
        result = codex.fetch_quota()
        assert result["percent_left"] == 60


class TestCodexQueryDb:
    def test_missing_db_returns_none(self, tmp_path):
        with patch.object(codex, "CODEX_STATE_DB", str(tmp_path / "nonexistent.sqlite")):
            assert codex._query_db() is None

"""Tests for ai_quota.cache — read/write helpers."""
import json
import os

from ai_quota.cache import read_cache, read_cache_updated, write_cache


class TestWriteCache:
    def test_roundtrip(self, tmp_path):
        path = str(tmp_path / "test.cache")
        entries = [{"label": "session", "percent": 42}]
        write_cache(path, entries)
        assert read_cache(path) == entries

    def test_atomic_write(self, tmp_path):
        path = str(tmp_path / "test.cache")
        entries = [{"model": "gemini-2.0-flash", "used_pct": 30.0}]
        write_cache(path, entries)
        # Verify temp file is cleaned up
        assert not os.path.exists(path + ".tmp")

    def test_overwrites_existing(self, tmp_path):
        path = str(tmp_path / "test.cache")
        write_cache(path, [{"a": 1}])
        write_cache(path, [{"b": 2}])
        assert read_cache(path) == [{"b": 2}]


class TestReadCache:
    def test_missing_file_returns_empty(self, tmp_path):
        assert read_cache(str(tmp_path / "nonexistent.cache")) == []

    def test_corrupt_json_returns_empty(self, tmp_path):
        path = str(tmp_path / "bad.cache")
        path_obj = tmp_path / "bad.cache"
        path_obj.write_text("not json")
        assert read_cache(path) == []

    def test_missing_entries_key_returns_empty(self, tmp_path):
        path = str(tmp_path / "no_entries.cache")
        (tmp_path / "no_entries.cache").write_text(json.dumps({"updated": 123}))
        assert read_cache(path) == []

    def test_empty_entries_list(self, tmp_path):
        path = str(tmp_path / "empty.cache")
        write_cache(path, [])
        assert read_cache(path) == []


class TestReadCacheUpdated:
    def test_returns_timestamp_after_write(self, tmp_path):
        import time
        path = str(tmp_path / "test.cache")
        before = time.time()
        write_cache(path, [{"label": "session", "percent": 50}])
        after = time.time()
        ts = read_cache_updated(path)
        assert ts is not None
        assert before <= ts <= after

    def test_missing_file_returns_none(self, tmp_path):
        assert read_cache_updated(str(tmp_path / "nonexistent.cache")) is None

    def test_corrupt_json_returns_none(self, tmp_path):
        path = str(tmp_path / "bad.cache")
        (tmp_path / "bad.cache").write_text("not json")
        assert read_cache_updated(path) is None

    def test_missing_updated_key_returns_none(self, tmp_path):
        path = str(tmp_path / "no_updated.cache")
        (tmp_path / "no_updated.cache").write_text(json.dumps({"entries": []}))
        assert read_cache_updated(path) is None

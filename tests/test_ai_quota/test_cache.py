"""Tests for ai_quota.cache — read/write helpers."""
import json
import os
import tempfile

import pytest

from ai_quota.cache import read_cache, write_cache


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

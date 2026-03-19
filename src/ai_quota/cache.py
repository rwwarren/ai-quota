"""Shared cache read/write for all AI quota providers."""
from __future__ import annotations

import json
import os
import time


def write_cache(path: str, entries: list[dict]) -> None:
    """Atomically write entries to a JSON cache file."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"updated": time.time(), "entries": entries}, f)
    os.replace(tmp, path)


def read_cache(path: str) -> list[dict]:
    """Read entries from a JSON cache file; returns [] on any error."""
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("entries", [])
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return []

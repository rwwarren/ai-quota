"""OpenCode quota provider.

Runs `opencode stats` and parses the output.
"""
from __future__ import annotations

import os
import re
import subprocess

from ai_quota.cache import read_cache as _read
from ai_quota.cache import read_cache_updated as _read_updated
from ai_quota.cache import write_cache as _write

CACHE_FILE = os.environ.get("OPENCODE_USAGE_CACHE", "/tmp/opencode-usage.cache")


def parse_usage(raw: str) -> list[dict]:
    """Parse `opencode stats` output into a list of quota entries."""
    entry = {}

    clean = re.sub(r"[■□╌▬┌─┐│├┤┘└┴┬┼█┃┏┓┗┛┣┫┳┻╋━]", " ", raw)

    m = re.search(r"Sessions\s+(\d+)", clean)
    if m:
        entry["sessions"] = int(m.group(1))
    m = re.search(r"Messages\s+(\d+)", clean)
    if m:
        entry["messages"] = int(m.group(1))
    m = re.search(r"Days\s+(\d+)", clean)
    if m:
        entry["days"] = int(m.group(1))

    m = re.search(r"Total Cost\s+(\$[\d\.]+)", clean)
    if m:
        entry["total_cost"] = m.group(1)
    m = re.search(r"Avg Cost/Day\s+(\$[\d\.]+)", clean)
    if m:
        entry["avg_cost_day"] = m.group(1)
    m = re.search(r"Avg Tokens/Session\s+([\d\.]+[KMB]?)", clean)
    if m:
        entry["avg_tokens_session"] = m.group(1)
    m = re.search(r"Median Tokens/Session\s+([\d\.]+[KMB]?)", clean)
    if m:
        entry["median_tokens_session"] = m.group(1)
    m = re.search(r"Input\s+([\d\.]+[KMB]?)", clean)
    if m:
        entry["input_tokens"] = m.group(1)
    m = re.search(r"Output\s+([\d\.]+[KMB]?)", clean)
    if m:
        entry["output_tokens"] = m.group(1)
    m = re.search(r"Cache Read\s+([\d\.]+[KMB]?)", clean)
    if m:
        entry["cache_read"] = m.group(1)
    m = re.search(r"Cache Write\s+([\d\.]+[KMB]?)", clean)
    if m:
        entry["cache_write"] = m.group(1)

    if not entry:
        return []

    return [entry]


def fetch_live() -> list[dict]:  # pragma: no cover — requires opencode CLI
    """Run `opencode stats` and return parsed entries."""
    try:
        result = subprocess.run(["opencode", "stats"], capture_output=True, text=True, check=True)
        raw = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', result.stdout)
        return parse_usage(raw)
    except Exception:
        return []


def read_cache() -> list[dict]:
    return _read(CACHE_FILE)


def read_cache_last_checked() -> float | None:
    return _read_updated(CACHE_FILE)


def write_cache(entries: list[dict]) -> None:
    _write(CACHE_FILE, entries)


def fmt_short(entries: list[dict]) -> str:
    if not entries:
        return "opencode: no data"
    e = entries[0]
    return (
        f"OpenCode: {e.get('total_cost', '$0.00')}"
        f" | {e.get('input_tokens', '0')} in"
        f" | {e.get('output_tokens', '0')} out"
    )


def fmt_slack(entries: list[dict]) -> str:
    if not entries:
        return ":warning: No OpenCode usage data found."
    e = entries[0]
    lines = ["*OpenCode Usage*"]
    lines.append(f"• Total Cost: `{e.get('total_cost', '$0.00')}`")
    lines.append(
        f"• Tokens: `{e.get('input_tokens', '0')} In`"
        f" / `{e.get('output_tokens', '0')} Out`"
    )
    lines.append(
        f"• Activity: `{e.get('sessions', 0)} Sessions`"
        f" / `{e.get('messages', 0)} Messages`"
    )
    if e.get("cache_read") or e.get("cache_write"):
        lines.append(
            f"• Cache: `{e.get('cache_read', '0')} Read`"
            f" / `{e.get('cache_write', '0')} Write`"
        )
    return "\n".join(lines)

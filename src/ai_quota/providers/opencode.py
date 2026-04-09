"""OpenCode quota provider implementation."""
from __future__ import annotations
import os
import re
import subprocess
from pathlib import Path
from ai_quota.cache import read_cache, write_cache

CACHE_FILE = os.environ.get("OPENCODE_USAGE_CACHE", "/tmp/ai-quota/opencode-usage.cache")

def parse_usage(raw: str) -> dict:
    """Parse opencode stats output into structured data"""
    entry = {}
    clean = re.sub(r"[■□╌▬┌─┐│├┤┘└┴┬┼█┃┏┓┗┛┣┫┳┻╋━]", " ", raw)

    # Overview section
    m = re.search(r"Sessions\s+(\d+)", clean)
    if m:
        entry["sessions"] = int(m.group(1))
    m = re.search(r"Messages\s+(\d+)", clean)
    if m:
        entry["messages"] = int(m.group(1))
    m = re.search(r"Days\s+(\d+)", clean)
    if m:
        entry["days"] = int(m.group(1))

    # Cost & Tokens section
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

    return entry

def fetch_live() -> dict:
    """Run opencode stats and parse output"""
    try:
        result = subprocess.run(
            ["opencode", "stats"],
            capture_output=True,
            text=True,
            check=True
        )
        return parse_usage(result.stdout)
    except Exception as e:
        print(f"Error fetching OpenCode stats: {e}")
        return {}

# Ensure cache directory exists
os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
# Register cache handling
write_cache(CACHE_FILE, read_cache(CACHE_FILE))
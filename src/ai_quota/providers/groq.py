"""Groq API quota provider.

Fetches rate limit information from the Groq API using the GROQ_API_KEY
environment variable and parses the rate limit headers from the response.

Each call to ``fetch_live()`` makes a lightweight GET /models request and
reads the ``x-ratelimit-*`` headers that Groq includes in every response.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.request import Request, urlopen

from ai_quota.cache import read_cache as _read
from ai_quota.cache import write_cache as _write
from ai_quota.formatters import fmt_bar, fmt_reset

CACHE_FILE = os.environ.get("GROQ_USAGE_CACHE", "/tmp/groq-usage.cache")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_API_BASE = os.environ.get("GROQ_API_BASE", "https://api.groq.com/openai/v1")


# ---------------------------------------------------------------------------
# Parsing (pure — no external deps, easily testable)
# ---------------------------------------------------------------------------

def parse_reset_duration(reset_str: str) -> str | None:
    """Parse a Groq rate-limit reset string into an ISO timestamp.

    Groq reset strings look like ``'59.814s'``, ``'1m30s'``, or ``'2m'``.
    Returns ``None`` when the string is empty or unparseable.
    """
    if not reset_str:
        return None
    m = re.fullmatch(r"(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", reset_str.strip())
    if not m or not (m.group(1) or m.group(2)):
        return None
    total_seconds = 0.0
    if m.group(1):
        total_seconds += int(m.group(1)) * 60
    if m.group(2):
        total_seconds += float(m.group(2))
    if total_seconds == 0:
        return None
    return (datetime.now() + timedelta(seconds=total_seconds)).isoformat()


def parse_rate_limit_headers(headers: dict) -> list[dict]:
    """Parse Groq ``x-ratelimit-*`` headers into a list of usage entries.

    Returns up to two entries — one for token throughput, one for request
    rate — using the same ``{"model", "used_pct", "reset_ts"}`` shape as
    the Gemini / Codex providers.

    Args:
        headers: A case-insensitive mapping of HTTP response headers.
    """
    entries = []

    pairs = [
        ("tokens/min",   "x-ratelimit-limit-tokens",   "x-ratelimit-remaining-tokens",   "x-ratelimit-reset-tokens"),
        ("requests/min", "x-ratelimit-limit-requests", "x-ratelimit-remaining-requests", "x-ratelimit-reset-requests"),
    ]
    for label, limit_key, remaining_key, reset_key in pairs:
        limit_val = headers.get(limit_key)
        remaining_val = headers.get(remaining_key)
        if not limit_val or not remaining_val:
            continue
        try:
            limit = int(limit_val)
            remaining = int(remaining_val)
            if limit <= 0:
                continue
            used_pct = (limit - remaining) / limit * 100.0
            entries.append({
                "model": label,
                "used_pct": used_pct,
                "reset_ts": parse_reset_duration(headers.get(reset_key, "")),
                "limit": limit,
                "remaining": remaining,
            })
        except (ValueError, ZeroDivisionError):
            continue

    return entries


# ---------------------------------------------------------------------------
# Live fetch
# ---------------------------------------------------------------------------

def fetch_live() -> list[dict]:
    """Make a lightweight Groq API request and return rate-limit entries.

    Reads ``GROQ_API_KEY`` from the environment.  Returns ``[]`` when the
    key is absent or the request fails.
    """
    api_key = GROQ_API_KEY
    if not api_key:
        return []
    url = f"{GROQ_API_BASE}/models"
    req = Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urlopen(req, timeout=10) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
    except (URLError, OSError):
        return []
    return parse_rate_limit_headers(headers)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def read_cache() -> list[dict]:
    return _read(CACHE_FILE)


def write_cache(entries: list[dict]) -> None:
    _write(CACHE_FILE, entries)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def fmt_short(entries: list[dict]) -> str:
    parts = []
    for e in entries:
        pct = e.get("used_pct", 0)
        parts.append(f"{e['model']}: {pct:.0f}%")
    return " | ".join(parts)


def fmt_slack(entries: list[dict]) -> str:
    if not entries:
        return ":warning: No Groq usage data available."
    lines = ["*Groq Usage*"]
    for e in entries:
        used = e.get("used_pct", 0)
        bar, emoji = fmt_bar(used)
        remaining = e.get("remaining", "?")
        limit = e.get("limit", "?")
        lines.append(f"{emoji} `{e['model']:15} [{bar}] {used:4.0f}% used  ({remaining}/{limit} remaining)`")
        reset = fmt_reset(e.get("reset_ts"))
        if reset:
            lines.append(f"   _{reset}_")
    return "\n".join(lines)

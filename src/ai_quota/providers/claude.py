"""Claude Code quota provider.

Spawns `claude` in a virtual terminal, runs /usage, and parses the output.
"""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime, timedelta

from ai_quota.cache import read_cache as _read
from ai_quota.cache import read_cache_updated as _read_updated
from ai_quota.cache import write_cache as _write
from ai_quota.formatters import fmt_bar, fmt_reset

CACHE_FILE = os.environ.get("CLAUDE_USAGE_CACHE", "/tmp/cc-usage-pct.cache")
TIMEOUT = int(os.environ.get("CLAUDE_USAGE_TIMEOUT", "30"))
WORK_DIR = os.environ.get("CLAUDE_USAGE_DIR", os.path.expanduser("~"))
ROWS = 60
COLS = 120


# ---------------------------------------------------------------------------
# Parsing (pure — no external deps, easily testable)
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Collapse whitespace and strip terminal rendering artifacts from pyte output."""
    text = re.sub(r"\s{2,}", " ", text.strip())
    text = re.sub(r"(\s+[a-z]\b){2,}\s*$", "", text)
    text = re.sub(r"\bRese?\s*t?s?\b(?=\s+\w)", "Resets", text, flags=re.IGNORECASE)
    text = re.sub(r"\bRe\s+sets\b", "Resets", text, flags=re.IGNORECASE)
    return text.strip()


def _normalize_label(raw: str) -> str:
    """Map raw pyte labels to canonical names."""
    low = raw.lower()
    if "session" in low:
        return "session"
    if "week" in low:
        return "week"
    if "extra" in low or "add-on" in low or "addon" in low:
        return "Extra usage"
    if "daily" in low or "day" in low:
        return "daily"
    return raw


def parse_usage(lines: list[str]) -> list[dict]:
    """Parse /usage screen lines into a list of quota entries.

    Each entry: {"label": str, "percent": int, "reset_ts": str|None, "cost": str}
    """
    entries = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = re.search(r"(\d+)%\s*used", line)
        if match:
            pct = int(match.group(1))
            label = ""
            for j in range(i - 1, max(i - 3, -1), -1):
                candidate = _clean(lines[j])
                if candidate and not re.match(r"^[█▌▏\s]+$", candidate):
                    label = _normalize_label(candidate)
                    break

            reset_info = ""
            cost_info = ""
            for k in range(i + 1, min(i + 3, len(lines))):
                candidate = _clean(lines[k])
                low = candidate.lower()
                if not candidate or "% used" in low:
                    break
                is_reset = bool(re.search(r"rese\s*t?s?\b", low))
                if "$" in candidate and not reset_info:
                    if is_reset:
                        reset_info = candidate
                    else:
                        cost_info = candidate
                elif is_reset:
                    reset_info = candidate

            entries.append({
                "label": label,
                "percent": pct,
                "reset_ts": _parse_reset_ts(reset_info),
                "cost": cost_info,
            })
        i += 1
    return entries


def _parse_reset_ts(raw: str) -> str | None:
    """Parse a Claude reset string into an ISO timestamp.

    Input formats::

        'Resets 11pm (America/Los_Angeles)'
        'Resets Mar 19 at 10pm (America/Los_Angeles)'
        '$1.23 used of $5.00 Resets Mon'
    """
    if not raw:
        return None
    m = re.search(r"[Rr]esets?\s+(.+)", raw)
    if not m:
        return None
    rest = re.sub(r"\s*\([^)]*\)\s*$", "", m.group(1).strip()).strip()

    now = datetime.now()
    target = None

    m_time = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", rest, re.IGNORECASE)
    if m_time:
        hour = int(m_time.group(1))
        minute = int(m_time.group(2) or 0)
        ampm = m_time.group(3).lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)

    if target is None:
        m_date = re.match(
            r"^(\w{3})\s+(\d{1,2})\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)$",
            rest, re.IGNORECASE,
        )
        if m_date:
            month_str, day = m_date.group(1), int(m_date.group(2))
            hour, minute = int(m_date.group(3)), int(m_date.group(4) or 0)
            ampm = m_date.group(5).lower()
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            try:
                target = datetime.strptime(f"{month_str} {day} {now.year}", "%b %d %Y")
                target = target.replace(hour=hour, minute=minute)
                if target <= now:
                    target = target.replace(year=now.year + 1)
            except ValueError:
                pass

    return target.isoformat() if target else None


# ---------------------------------------------------------------------------
# Live fetch (requires `claude` CLI + pexpect/pyte)
# ---------------------------------------------------------------------------

def fetch_live() -> list[dict]:
    """Spawn `claude`, run /usage, return parsed entries."""
    import pexpect
    import pyte

    os.chdir(WORK_DIR)
    screen = pyte.Screen(COLS, ROWS)
    stream = pyte.Stream(screen)

    child = pexpect.spawn("claude", encoding="utf-8", timeout=TIMEOUT, dimensions=(ROWS, COLS))

    while True:
        i = child.expect(
            [r"Yes.*trust", r"[❯>╭]", pexpect.TIMEOUT, pexpect.EOF],
            timeout=TIMEOUT,
        )
        if i == 0:
            child.sendline("")
        elif i == 1:
            break
        else:
            print("Timed out waiting for Claude prompt", file=sys.stderr)
            sys.exit(1)

    try:
        while True:
            child.expect(r".+", timeout=1)
    except pexpect.TIMEOUT:
        pass

    screen.reset()
    time.sleep(0.5)
    child.send("/usage")
    time.sleep(1)
    child.send("\r")

    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            child.expect(r".+", timeout=1)
            raw = child.match.group(0) if child.match else ""
            if raw:
                stream.feed(raw)
        except pexpect.TIMEOUT:
            continue
        except pexpect.EOF:
            break

    lines = [screen.display[r].rstrip() for r in range(ROWS) if screen.display[r].rstrip()]

    child.sendline("/exit")
    try:
        child.expect(pexpect.EOF, timeout=5)
    except Exception:
        child.close()

    if os.environ.get("DEBUG"):
        for idx, line in enumerate(lines):
            print(f"[{idx:3d}] {line!r}", file=sys.stderr)

    return parse_usage(lines)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def read_cache() -> list[dict]:
    return _read(CACHE_FILE)


def read_cache_last_checked() -> float | None:
    return _read_updated(CACHE_FILE)


def write_cache(entries: list[dict]) -> None:
    _write(CACHE_FILE, entries)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def fmt_short(entries: list[dict]) -> str:
    return " | ".join(f"{e['label']}: {e['percent']}%" for e in entries)


def fmt_pretty(entries: list[dict]) -> str:
    lines = []
    for e in entries:
        lines.append(f"{e['label']}: {e['percent']}% used")
        reset = fmt_reset(e.get("reset_ts"))
        if reset:
            lines.append(f"  {reset}")
        if e.get("cost"):
            lines.append(f"  {e['cost']}")
    return "\n".join(lines)


def fmt_slack(entries: list[dict]) -> str:
    lines = ["*Claude Code Usage*"]
    for e in entries:
        bar, emoji = fmt_bar(e["percent"])
        lines.append(f"{emoji} `{e['label']:25} [{bar}] {e['percent']:4d}% used`")
        detail = e.get("cost") or fmt_reset(e.get("reset_ts")) or ""
        if detail:
            lines.append(f"   _{detail}_")
    return "\n".join(lines)

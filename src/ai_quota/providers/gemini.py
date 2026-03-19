"""Gemini CLI quota provider.

Spawns `gemini` in a virtual terminal, runs /stats, and parses the output.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta

from ai_quota.cache import read_cache as _read, write_cache as _write
from ai_quota.formatters import fmt_bar, fmt_reset

CACHE_FILE = os.environ.get("GEMINI_USAGE_CACHE", "/tmp/gemini-usage.cache")


# ---------------------------------------------------------------------------
# Parsing (pure — no external deps, easily testable)
# ---------------------------------------------------------------------------

def parse_usage(raw: str) -> list[dict]:
    """Parse /stats screen output into a list of quota entries.

    Each entry: {"model": str, "used_pct": float, "reset_ts": str|None}
    """
    entries = []
    pattern = re.compile(r"([\w\.-]+)\s+[\d,.-]+\s+(\d+\.?\d*)\s*%")

    for line in raw.splitlines():
        clean = re.sub(r"[│┤┐└┴┬├─┼█░┃┏┓┗┛┣┫┳┻╋━]", " ", line)
        match = pattern.search(clean)
        if match:
            model = match.group(1).strip()
            if model.lower() in ["model", "reqs", "usage", "total"]:
                continue
            try:
                rem = float(match.group(2))
                used_pct = 100.0 - rem
                reset = "Unknown"
                reset_match = re.search(r"(resets in [^│\n]+)", line)
                if reset_match:
                    reset = reset_match.group(1).strip()
                entries.append({
                    "model": model,
                    "used_pct": used_pct,
                    "reset_ts": _parse_reset_ts(reset),
                })
            except ValueError:
                continue
    return entries


def _parse_reset_ts(raw: str) -> str | None:
    """Parse a Gemini reset string into an ISO timestamp.

    Input formats::

        'resets in 3h 24m'
        'resets in 3 days'
        'Unknown'
    """
    if not raw or raw == "Unknown":
        return None
    m = re.match(r"resets\s+in\s+(.+)", raw, re.IGNORECASE)
    if not m:
        return None

    duration_str = m.group(1).strip()
    total_minutes = 0
    d = re.search(r"(\d+)\s*d", duration_str)
    h = re.search(r"(\d+)\s*h", duration_str)
    mn = re.search(r"(\d+)\s*m", duration_str)
    if d:
        total_minutes += int(d.group(1)) * 24 * 60
    if h:
        total_minutes += int(h.group(1)) * 60
    if mn:
        total_minutes += int(mn.group(1))
    if total_minutes == 0:
        return None

    target = datetime.now() + timedelta(minutes=total_minutes)
    return target.isoformat()


# ---------------------------------------------------------------------------
# Live fetch (requires `gemini` CLI + pexpect/pyte)
# ---------------------------------------------------------------------------

def fetch_live() -> list[dict]:
    """Spawn `gemini`, run /stats, return parsed entries."""
    import pexpect
    import pyte

    TIMEOUT = 45
    ROWS, COLS = 40, 160
    env = os.environ.copy()
    env["PAGER"] = "cat"
    env["TERM"] = "xterm-256color"

    screen = pyte.Screen(COLS, ROWS)
    stream = pyte.Stream(screen)

    log_path = os.environ.get("GEMINI_USAGE_LOG", "/tmp/gemini-usage.log")

    try:
        child = pexpect.spawn("gemini", env=env, encoding="utf-8", dimensions=(ROWS, COLS))
        with open(log_path, "w", encoding="utf-8") as log_file:
            child.logfile_read = log_file
            child.expect("Type your message", timeout=TIMEOUT)
            time.sleep(5)
            try:
                while True:
                    child.read_nonblocking(size=8192, timeout=0.1)
            except Exception:
                pass

            child.send("/stats\r")
            time.sleep(2)
            child.send("\r")
            time.sleep(2)
            child.send("\r")

            deadline = time.time() + 20
            while time.time() < deadline:
                try:
                    char = child.read_nonblocking(size=1024, timeout=1)
                    if char:
                        stream.feed(char)
                except pexpect.TIMEOUT:
                    continue
                except pexpect.EOF:
                    break

            try:
                child.sendline("/exit")
                time.sleep(2)
                child.close(force=True)
            except Exception:
                pass
    except Exception:
        if "child" in dir():
            child.close(force=True)

    lines = []
    for row in range(ROWS):
        line = screen.display[row].rstrip()
        if line.strip():
            lines.append(line)

    raw = "\n".join(lines)
    return parse_usage(raw)


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
    return " | ".join(f"{e['model']}: {e['used_pct']:.1f}%" for e in entries)


def fmt_slack(entries: list[dict]) -> str:
    if not entries:
        return ":warning: No Gemini usage data found."
    lines = ["*Gemini CLI Usage*"]
    for e in entries:
        used = e["used_pct"]
        bar, emoji = fmt_bar(used)
        lines.append(f"{emoji} `{e['model']:25} [{bar}] {used:4.0f}% used`")
        reset = fmt_reset(e.get("reset_ts"))
        if reset:
            lines.append(f"   _{reset}_")
    return "\n".join(lines)

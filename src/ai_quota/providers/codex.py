"""Codex (OpenAI) quota provider.

Reads quota from two sources:
1. Codex TUI /status panel (via PTY)
2. Local SQLite database (~/.codex/state_5.sqlite)
"""
from __future__ import annotations

import fcntl
import os
import re
import select
import signal
import sqlite3
import struct
import subprocess
import time
from datetime import date, datetime

from ai_quota.cache import read_cache as _read
from ai_quota.cache import write_cache as _write
from ai_quota.formatters import fmt_bar, fmt_reset

CACHE_FILE = os.environ.get("CODEX_USAGE_CACHE", "/tmp/codex-usage.cache")
CODEX_STATE_DB = os.path.expanduser(
    os.environ.get("CODEX_STATE_DB", "~/.codex/state_5.sqlite")
)


# ---------------------------------------------------------------------------
# TUI spawning — get quota % from interactive codex /status panel
# ---------------------------------------------------------------------------

def _read_pty(master: int, timeout: float) -> bytes:
    """Read from PTY until timeout with no new data."""
    result = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r, _, _ = select.select([master], [], [], 0.3)
        if r:
            try:
                data = os.read(master, 8192)
                if not data:
                    break
                result += data
            except OSError:
                break
    return result


def _spawn_codex_and_read() -> str:
    """Spawn codex TUI, send /status, capture output with pyte."""
    import pty
    import termios

    import pyte

    master, slave = pty.openpty()
    winsize = struct.pack("HHHH", 80, 250, 0, 0)
    fcntl.ioctl(slave, termios.TIOCSWINSZ, winsize)

    env = os.environ.copy()
    env["TERM"] = "xterm-256color"

    try:
        proc = subprocess.Popen(
            ["codex"],
            stdin=slave, stdout=slave, stderr=slave,
            close_fds=True, env=env, preexec_fn=os.setsid,
        )
    except Exception:
        os.close(master)
        os.close(slave)
        raise
    os.close(slave)

    output = b""
    output += _read_pty(master, 4)
    os.write(master, b"\x1b[1;1R")
    time.sleep(0.3)
    os.write(master, b"\x1b[?62;c")
    time.sleep(0.3)
    os.write(master, b"\x1b]10;rgb:0000/0000/0000\x1b\\")
    time.sleep(2)
    output += _read_pty(master, 3)

    for c in "/status":
        os.write(master, c.encode())
        time.sleep(0.4)
    output += _read_pty(master, 1)
    os.write(master, b"\r")
    output += _read_pty(master, 5)

    screen = pyte.Screen(columns=250, lines=80)
    stream = pyte.Stream(screen)
    stream.feed(output.decode("utf-8", errors="replace"))
    rendered = "\n".join(line.rstrip() for line in screen.display)

    os.kill(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    os.close(master)
    return rendered


# ---------------------------------------------------------------------------
# Parsing (pure — no external deps, easily testable)
# ---------------------------------------------------------------------------

def parse_tui_output(text: str) -> dict:
    """Parse codex TUI /status output for model, quota, and reset info.

    Tries two sources:

    1. ``/status`` panel: ``Weekly limit: [...] 93% left (resets 14:39 on 21 Mar)``
    2. Status bar: ``gpt-5.2-codex medium · 100% left · ~/...``
    """
    info: dict = {}

    m = re.search(r"Model:\s+([\w.-]+)\s+\(reasoning\s+(\w+)", text)
    if m:
        info["model"] = m.group(1)
        info["reasoning_effort"] = m.group(2)

    m2 = re.search(r"Weekly limit:.*?(\d+)%\s+left", text)
    if m2:
        info["percent_left"] = int(m2.group(1))

    m3 = re.search(r"\(resets?\s+(\d{1,2}:\d{2})\s+on\s+(\d{1,2}\s+\w+)\)", text)
    if m3:
        info["resets_time"] = m3.group(1)
        info["resets_date"] = m3.group(2)

    m4 = re.search(r"Account:\s+(.+?)(?:\s*│|$)", text, re.MULTILINE)
    if m4:
        info["account"] = m4.group(1).strip()

    if "percent_left" not in info:
        sb = re.search(r"([\w.-]+)\s+\w+\s+·\s+(\d+)%\s+left\s+·", text)
        if sb:
            info.setdefault("model", sb.group(1))
            info["percent_left"] = int(sb.group(2))

    return info


def _parse_reset_ts(resets_time: str, resets_date: str) -> str | None:
    """Parse codex TUI time/date fields into an ISO timestamp.

    Args:
        resets_time: ``'14:39'`` (24h from TUI)
        resets_date: ``'21 Mar'``
    """
    if not resets_time:
        return None
    now = datetime.now()
    try:
        target = datetime.strptime(f"{resets_date} {now.year} {resets_time}", "%d %b %Y %H:%M")
        if target <= now:
            target = target.replace(year=now.year + 1)
        return target.isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Local DB — token counts from ~/.codex/state_5.sqlite
# ---------------------------------------------------------------------------

def _query_db() -> dict | None:
    """Read today's and all-time token usage from the Codex sqlite database."""
    if not os.path.exists(CODEX_STATE_DB):
        return None
    try:
        db = sqlite3.connect(f"file:{CODEX_STATE_DB}?mode=ro", uri=True)
        today_start = int(datetime.combine(date.today(), datetime.min.time()).timestamp())
        tomorrow_start = today_start + 86400

        rows = db.execute(
            "SELECT tokens_used FROM threads WHERE created_at >= ? AND created_at < ?",
            (today_start, tomorrow_start),
        ).fetchall()
        all_rows = db.execute("SELECT SUM(tokens_used), COUNT(*) FROM threads").fetchone()
        db.close()

        return {
            "today_tokens": sum(r[0] for r in rows),
            "today_sessions": len(rows),
            "all_time_tokens": all_rows[0] or 0,
            "all_time_sessions": all_rows[1] or 0,
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Top-level fetch
# ---------------------------------------------------------------------------

def fetch_quota() -> dict | None:
    """Spawn codex TUI, capture /status, return parsed info dict."""
    try:
        rendered = _spawn_codex_and_read()
        result = parse_tui_output(rendered)
        return result if result else None
    except Exception:
        return None


def fetch_live() -> list[dict]:
    """Fetch usage entries combining TUI quota and local DB token counts."""
    quota = fetch_quota()
    db = _query_db()

    if not quota and not db:
        return []

    model = (quota or {}).get("model", "codex")
    pct_left = (quota or {}).get("percent_left")
    used_pct = (100 - pct_left) if pct_left is not None else None

    resets_time = (quota or {}).get("resets_time", "")
    resets_date = (quota or {}).get("resets_date", "")
    reset_ts = _parse_reset_ts(resets_time, resets_date)

    entry = {
        "model": model,
        "used_pct": used_pct,
        "reset_ts": reset_ts,
        "today_tokens": (db or {}).get("today_tokens", 0),
        "today_sessions": (db or {}).get("today_sessions", 0),
        "all_time_tokens": (db or {}).get("all_time_tokens", 0),
        "all_time_sessions": (db or {}).get("all_time_sessions", 0),
        "date": date.today().isoformat(),
    }
    return [entry]


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
        pct = e.get("used_pct")
        pct_str = f"{pct:.0f}%" if pct is not None else "?"
        parts.append(f"{e['model']}: {pct_str}")
    return " | ".join(parts)


def fmt_slack(entries: list[dict]) -> str:
    if not entries:
        return ":warning: No Codex usage data available."
    lines = ["*Codex (OpenAI) Usage*"]
    for e in entries:
        used = e.get("used_pct")
        if used is not None:
            bar, emoji = fmt_bar(used)
            lines.append(f"{emoji} `{e['model']:25} [{bar}] {used:4.0f}% used`")
        else:
            lines.append(f":white_circle: `{e['model']:25} [unknown]`")
        reset = fmt_reset(e.get("reset_ts"))
        if reset:
            lines.append(f"   _{reset}_")
        tokens = e.get("today_tokens", 0)
        sessions = e.get("today_sessions", 0)
        all_tokens = e.get("all_time_tokens", 0)
        all_sessions = e.get("all_time_sessions", 0)
        lines.append(
            f"   Today: {tokens:,} tokens ({sessions} sessions) · "
            f"All-time: {all_tokens:,} tokens ({all_sessions} sessions)"
        )
    return "\n".join(lines)

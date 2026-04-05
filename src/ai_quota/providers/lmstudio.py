"""LM Studio quota provider.

Reads conversation JSON files from ~/.lmstudio/conversations/ and
aggregates token usage across all conversations.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from ai_quota.cache import read_cache as _read
from ai_quota.cache import read_cache_updated as _read_updated
from ai_quota.cache import write_cache as _write

CACHE_FILE = os.environ.get("LMSTUDIO_USAGE_CACHE", "/tmp/lmstudio-usage.cache")
CONVERSATIONS_DIR = Path(os.environ.get(
    "LMSTUDIO_CONVERSATIONS_DIR",
    os.path.expanduser("~/.lmstudio/conversations"),
))


def parse_conversations(conversations_dir: Path) -> list[dict]:
    """Read all conversation JSON files and aggregate token stats."""
    if not conversations_dir.is_dir():
        return []

    total_prompt = 0
    total_predicted = 0
    last_activity = 0
    last_info: dict | None = None

    for f in conversations_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        assistant_at = data.get("assistantLastMessagedAt", 0)
        user_at = data.get("userLastMessagedAt", 0)

        for msg in data.get("messages", []):
            selected_idx = msg.get("currentlySelected", 0)
            versions = msg.get("versions", [])
            if selected_idx >= len(versions):
                continue
            version = versions[selected_idx]

            for step in version.get("steps", []):
                stats = (step.get("genInfo") or {}).get("stats")
                if not stats:
                    continue

                prompt = stats.get("promptTokensCount", 0)
                predicted = stats.get("predictedTokensCount", 0)
                total_prompt += prompt
                total_predicted += predicted

                msg_time = max(assistant_at, user_at)
                if msg_time >= last_activity:
                    last_activity = msg_time
                    sender = version.get("senderInfo") or {}
                    last_info = {
                        "prompt_tokens": prompt,
                        "predicted_tokens": predicted,
                        "total_tokens": stats.get("totalTokensCount", prompt + predicted),
                        "model": sender.get("senderName", "Unknown"),
                        "time": msg_time,
                    }

    if total_prompt == 0 and total_predicted == 0:
        return []

    entry: dict = {
        "total_prompt_tokens": total_prompt,
        "total_predicted_tokens": total_predicted,
        "cumulative_total": total_prompt + total_predicted,
    }
    if last_info:
        entry["last_usage"] = {
            **last_info,
            "time": datetime.fromtimestamp(last_info["time"] / 1000).isoformat()
            if last_info["time"]
            else None,
        }

    return [entry]


def fetch_live() -> list[dict]:  # pragma: no cover — reads local files
    """Read LM Studio conversation files and return parsed entries."""
    return parse_conversations(CONVERSATIONS_DIR)


def read_cache() -> list[dict]:
    return _read(CACHE_FILE)


def read_cache_last_checked() -> float | None:
    return _read_updated(CACHE_FILE)


def write_cache(entries: list[dict]) -> None:
    _write(CACHE_FILE, entries)


def _fmt_tokens(n: int) -> str:
    """Format a token count with comma separators."""
    return f"{n:,}"


def fmt_short(entries: list[dict]) -> str:
    if not entries:
        return "lmstudio: no data"
    e = entries[0]
    return (
        f"LM Studio: {_fmt_tokens(e['total_prompt_tokens'])} prompt"
        f" | {_fmt_tokens(e['total_predicted_tokens'])} generated"
        f" | {_fmt_tokens(e['cumulative_total'])} total"
    )


def _relative_time(iso_str: str | None) -> str:
    """Convert an ISO timestamp to a human-readable relative string."""
    if not iso_str:
        return "unknown"
    try:
        dt = datetime.fromisoformat(iso_str)
        delta = datetime.now() - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} min{'s' if minutes != 1 else ''} ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        days = hours // 24
        return f"{days} day{'s' if days != 1 else ''} ago"
    except (ValueError, TypeError):
        return iso_str or "unknown"


def fmt_slack(entries: list[dict]) -> str:
    if not entries:
        return ":warning: No LM Studio usage data found."
    e = entries[0]
    lines = ["*LM Studio Usage*"]
    lines.append(f"• Prompt Tokens: `{_fmt_tokens(e['total_prompt_tokens'])}`")
    lines.append(f"• Generated Tokens: `{_fmt_tokens(e['total_predicted_tokens'])}`")
    lines.append(f"• Total: `{_fmt_tokens(e['cumulative_total'])}`")

    last = e.get("last_usage")
    if last:
        lines.append(f"• Last Model: `{last['model']}`")
        lines.append(f"• Last Usage: {_relative_time(last.get('time'))}")

    return "\n".join(lines)

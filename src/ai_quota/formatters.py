"""Shared formatting helpers for AI quota providers."""
from __future__ import annotations

from datetime import datetime


def fmt_reset(reset_ts: str | None) -> str:
    """Format an ISO reset timestamp as 'resets in Xh Ym (H:MM AM/PM)'.

    Computes relative time fresh at call time so cached data stays accurate.
    """
    if not reset_ts:
        return ""
    try:
        target = datetime.fromisoformat(reset_ts)
    except (ValueError, TypeError):
        return ""

    now = datetime.now()
    total_min = max(int((target - now).total_seconds()) // 60, 0)
    hours, mins = divmod(total_min, 60)
    time_12 = target.strftime("%I:%M %p").lstrip("0")

    if hours >= 24:
        days = hours // 24
        hours = hours % 24
        date_str = target.strftime("%b %-d ") + time_12
        return f"resets in {days}d {hours}h {mins}m ({date_str})"
    if hours > 0:
        return f"resets in {hours}h {mins}m ({time_12})"
    return f"resets in {mins}m ({time_12})"


def fmt_bar(used_pct: float, width: int = 20) -> tuple[str, str]:
    """Return (bar_string, slack_emoji) for a usage percentage."""
    filled = int(used_pct * width / 100)
    empty = width - filled
    bar = "\u2588" * filled + "\u2591" * empty
    if used_pct >= 80:
        emoji = ":red_circle:"
    elif used_pct >= 50:
        emoji = ":large_yellow_circle:"
    else:
        emoji = ":large_green_circle:"
    return bar, emoji

"""ai_quota — check Claude / Gemini / Codex quota usage and cache results.

Quick start::

    from ai_quota import get_usage, is_exhausted

    # Returns list[dict] for the given provider (reads cache by default)
    entries = get_usage("claude")

    # One-liner for fallback chains
    if is_exhausted("claude"):
        if is_exhausted("gemini"):
            use_codex()

Provider keys: ``"claude"``, ``"gemini"``, ``"codex"``, ``"kilo"``
"""
from __future__ import annotations

from ai_quota.providers import claude, codex, gemini, kilo

_PROVIDERS: dict[str, object] = {
    "claude": claude,
    "gemini": gemini,
    "codex": codex,
    "kilo": kilo,
}


def get_usage(provider: str, *, cached: bool = True) -> list[dict]:
    """Return quota entries for *provider*.

    Args:
        provider: One of ``"claude"``, ``"gemini"``, ``"codex"``, ``"kilo"``.
        cached:   If ``True`` (default), read from the local cache file.
                  If ``False``, spawn the CLI tool live.

    Returns:
        A list of dicts.  Claude entries have keys ``label``, ``percent``,
        ``reset_ts``, ``cost``; Gemini/Codex entries have ``model``,
        ``used_pct``, ``reset_ts`` (plus token counts for Codex).
        Kilo entries have ``total_cost``, ``input_tokens``, etc.
    """
    mod = _PROVIDERS.get(provider)
    if mod is None:
        raise ValueError(f"Unknown provider {provider!r}. Choose from: {list(_PROVIDERS)}")
    if cached:
        return mod.read_cache()  # type: ignore[attr-defined]
    return mod.fetch_live()  # type: ignore[attr-defined]


def get_cache_last_checked(provider: str) -> float | None:
    """Return the Unix timestamp when the cache was last written, or None.

    Args:
        provider: One of ``"claude"``, ``"gemini"``, ``"codex"``.

    Returns:
        A float Unix timestamp, or ``None`` if no cache exists yet.
    """
    mod = _PROVIDERS.get(provider)
    if mod is None:
        raise ValueError(f"Unknown provider {provider!r}. Choose from: {list(_PROVIDERS)}")
    return mod.read_cache_last_checked()  # type: ignore[attr-defined]


def is_exhausted(provider: str) -> bool:
    """Return ``True`` if *provider*'s quota is at or above 100%.

    Reads from cache only (instant, no subprocess).  Returns ``False``
    when no cached data is available so callers can fall through safely.
    """
    entries = get_usage(provider, cached=True)
    if not entries:
        return False
    if provider == "claude":
        session = next((e for e in entries if e.get("label") == "session"), None)
        return session is not None and session.get("percent", 0) >= 100
    return all(e.get("used_pct", 0) >= 100 for e in entries)

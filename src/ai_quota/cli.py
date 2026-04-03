"""Unified CLI for ai-quota.

Usage::

    ai-quota claude [--json | --short | --slack | --pretty]
    ai-quota gemini [--json | --short | --slack]
    ai-quota codex  [--json | --short | --slack | --pretty]
    ai-quota kilo   [--json | --short | --slack]
    ai-quota all    [--short | --slack | --refresh]   # all providers

    # Use cached data (instant, no subprocess)
    ai-quota claude --cached [--short | --slack | --json]

    # Fetch live and write to cache
    ai-quota claude --refresh
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from ai_quota.providers import claude, codex, gemini, kilo

PROVIDER_TIMEOUT = int(os.environ.get("AI_QUOTA_PROVIDER_TIMEOUT", "60"))

_MODS = {"claude": claude, "gemini": gemini, "codex": codex, "kilo": kilo}


def _usage_and_exit() -> None:
    print(__doc__, file=sys.stderr)
    sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    args = (argv if argv is not None else sys.argv[1:])[:]

    if not args:
        _usage_and_exit()

    provider_name = args.pop(0)

    if provider_name == "all":
        _run_all(args)
        return

    mod = _MODS.get(provider_name)
    if mod is None:
        print(f"Unknown provider {provider_name!r}. Choose from: {list(_MODS)} or 'all'",
              file=sys.stderr)
        sys.exit(1)

    mode = args[0] if args else "--pretty"
    fmt = args[1] if len(args) > 1 else "--short"

    if mode == "--cached":
        entries = mod.read_cache()
        if not entries:
            print("No cached usage data", file=sys.stderr)
            sys.exit(1)
        _print(mod, entries, fmt)
        return

    entries = mod.fetch_live()
    if not entries:
        print("No usage data found", file=sys.stderr)
        sys.exit(1)

    if mode == "--refresh":
        mod.write_cache(entries)
        print(mod.fmt_short(entries))
        return

    _print(mod, entries, mode)


def _print(mod, entries: list[dict], fmt: str) -> None:
    if fmt == "--json":
        print(json.dumps(entries, indent=2))
    elif fmt == "--slack":
        print(mod.fmt_slack(entries))
    elif fmt == "--short":
        print(mod.fmt_short(entries))
    elif hasattr(mod, "fmt_pretty") and fmt in ("--pretty", ""):
        print(mod.fmt_pretty(entries))
    else:
        print(mod.fmt_short(entries))


def _fetch_with_timeout(name: str, mod, timeout: int) -> list[dict]:
    """Run a provider's fetch_live() with a hard timeout."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(mod.fetch_live)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            print(f"{name}: timed out after {timeout}s", file=sys.stderr)
            return []


def _run_all(args: list[str]) -> None:
    refresh = "--refresh" in args
    remaining = [a for a in args if a != "--refresh"]
    fmt = remaining[0] if remaining else "--short"

    if refresh:
        for name, mod in _MODS.items():
            entries = _fetch_with_timeout(name, mod, PROVIDER_TIMEOUT)
            if entries:
                mod.write_cache(entries)
                print(f"{name}: {mod.fmt_short(entries)}")
            else:
                print(f"{name}: no usage data", file=sys.stderr)
        return

    parts = []
    for name, mod in _MODS.items():
        entries = mod.read_cache()
        if entries:
            parts.append(mod.fmt_short(entries) if fmt != "--slack" else mod.fmt_slack(entries))
        else:
            parts.append(f"{name}: (no cached data)")
    print("\n".join(parts) if fmt == "--slack" else " | ".join(parts))


if __name__ == "__main__":
    main()

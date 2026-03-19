"""Unified CLI for ai-quota.

Usage::

    ai-quota claude [--json | --short | --slack | --pretty]
    ai-quota gemini [--json | --short | --slack]
    ai-quota codex  [--json | --short | --slack | --pretty]
    ai-quota all    [--short | --slack]   # all providers

    # Use cached data (instant, no subprocess)
    ai-quota claude --cached [--short | --slack | --json]

    # Fetch live and write to cache
    ai-quota claude --refresh
"""
from __future__ import annotations

import json
import sys

from ai_quota.providers import claude, codex, gemini

_MODS = {"claude": claude, "gemini": gemini, "codex": codex}


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


def _run_all(args: list[str]) -> None:
    fmt = args[0] if args else "--short"
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

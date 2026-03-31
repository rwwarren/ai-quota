# CLAUDE.md

## Project

Unified CLI and Python API for monitoring quota usage across AI coding assistants (Claude Code, Gemini CLI, Codex, Kilo). Spawns each provider's CLI in a PTY (or subprocess), parses terminal output via `pyte` or regex, and caches results as atomic JSON.

## Stack

- **Python:** 3.11+ (tested on 3.11–3.13 in CI)
- **Key deps:** `pyte`, `pexpect`
- **Dev deps:** `pytest`, `pytest-cov`, `pytest-mock`, `ruff`

## Commands

```bash
# Install (editable + dev tools)
pip install -e ".[dev]"

# Tests
pytest

# Tests with coverage (80% minimum enforced)
pytest --cov=ai_quota --cov-report=term-missing --cov-fail-under=80

# Lint
ruff check src tests

# Format
ruff format src tests
```

## Project Structure

```
src/ai_quota/
  __init__.py          # Public API: get_usage(), is_exhausted()
  cli.py               # Unified CLI entry point
  cache.py             # Atomic JSON cache helpers
  formatters.py        # Progress bars, reset time formatting
  providers/
    claude.py          # Claude Code provider (PTY + /usage)
    gemini.py          # Gemini CLI provider (PTY + /stats)
    codex.py           # Codex provider (PTY + /status + SQLite)
    kilo.py            # Kilo provider (subprocess + stats)
tests/test_ai_quota/   # pytest suite
bin/statusline.sh      # Claude Code terminal status line formatter
```

## Conventions

- Live-fetch functions (`fetch_live`, `_spawn_codex_and_read`, `_read_pty`) are excluded from coverage — they require real CLI tools at runtime
- All configuration via environment variables (see README for full list)
- `ruff` line length is 100; E501 (line too long) is ignored
- Cache files are atomic writes to `/tmp/` by default

## See also

See ~/CLAUDE.md for global conventions.

# ai-quota

[![CI](https://github.com/rwwarren/ai-quota/actions/workflows/ci.yml/badge.svg)](https://github.com/rwwarren/ai-quota/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/rwwarren/ai-quota/branch/main/graph/badge.svg)](https://codecov.io/gh/rwwarren/ai-quota)

Unified CLI and Python API for monitoring quota usage across AI coding assistants: **Claude Code**, **Gemini CLI**, **Codex**, and **Kilo**.

## Features

- **Multi-provider** — Query Claude Code, Gemini, Codex, and Kilo from one tool
- **CLI + Python API** — Use from the terminal or import in scripts
- **Caching** — Atomic JSON cache for instant reads; refresh on demand
- **Multiple output formats** — Plain text, JSON, Slack-friendly markdown, pretty progress bars
- **Reset countdowns** — Shows when quota resets in relative and absolute time (where available)
- **Token tracking** — Codex and Kilo providers track token usage and costs
- **Status line** — Bash script for Claude Code terminal status line integration

## Installation

```bash
# Install in editable mode
pip install -e .

# With dev tools (pytest, ruff)
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Usage

### CLI

```bash
# Check a single provider
ai-quota claude [--json | --short | --slack | --pretty]
ai-quota gemini [--json | --short | --slack]
ai-quota codex  [--json | --short | --slack | --pretty]
ai-quota kilo   [--json | --short | --slack]

# Check all providers
ai-quota all [--short | --slack]

# Use cached data (instant)
ai-quota claude --cached [--short | --slack | --json]

# Force a fresh fetch + update cache
ai-quota claude --refresh
```

### Python API

```python
from ai_quota import get_usage, is_exhausted

# Read from cache (default)
entries = get_usage("claude")

# Fetch live data
entries = get_usage("gemini", cached=False)

# Quick check for fallback logic
if is_exhausted("claude"):
    use_fallback_provider()
```

### Status Line

`bin/statusline.sh` formats Claude Code quota data for terminal status lines, showing context window usage, session/weekly/extra quota with color-coded progress bars and reset countdowns.

## How It Works

Each provider spawns its respective CLI tool in a PTY, sends a status command (`/usage`, `/stats`, `/status`), and parses the terminal output using [pyte](https://github.com/selectel/pyte) (a virtual terminal emulator). Results are normalized into a common format and cached as atomic JSON writes.

| Provider | CLI Tool | Command | Extra Data |
|----------|----------|---------|------------|
| Claude | `claude` | `/usage` | Cost breakdown |
| Gemini | `gemini` | `/stats` | Model name |
| Codex | `codex` | `/status` | Token counts via SQLite |
| Kilo | `kilo` | `stats` | Costs, tokens, and tool usage |

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_USAGE_CACHE` | `/tmp/cc-usage-pct.cache` | Claude cache path |
| `CLAUDE_USAGE_TIMEOUT` | `30` | Timeout in seconds |
| `CLAUDE_USAGE_DIR` | `~` | Working directory for Claude CLI |
| `GEMINI_USAGE_CACHE` | `/tmp/gemini-usage.cache` | Gemini cache path |
| `GEMINI_USAGE_LOG` | `/tmp/gemini-usage.log` | Gemini debug log path |
| `CODEX_USAGE_CACHE` | `/tmp/codex-usage.cache` | Codex cache path |
| `CODEX_STATE_DB` | `~/.codex/state_5.sqlite` | Codex SQLite DB path |
| `DEBUG` | — | Enable debug output |

## Project Structure

```
ai-quota/
├── bin/statusline.sh          # Claude Code status line formatter
├── src/ai_quota/
│   ├── __init__.py            # Public API: get_usage(), is_exhausted()
│   ├── cli.py                 # Unified CLI
│   ├── cache.py               # Atomic JSON cache helpers
│   ├── formatters.py          # Progress bars, reset time formatting
│   └── providers/
│       ├── claude.py          # Claude Code provider
│       ├── gemini.py          # Gemini CLI provider
│       └── codex.py           # Codex/OpenAI provider
├── tests/test_ai_quota/       # pytest suite
└── pyproject.toml             # Build config & dependencies
```

## Development

```bash
# Run tests
pytest

# Run with coverage (enforces 80% minimum)
pytest --cov=ai_quota --cov-report=term-missing --cov-fail-under=80

# Lint & format
ruff check src tests
ruff format src tests
```

CI runs on every push and PR via GitHub Actions (Python 3.11–3.13), with ruff linting, pytest, and coverage uploaded to Codecov.

## See Also

- [cc-usage-bar](https://github.com/lionhylra/cc-usage-bar) — Native macOS menu bar app for Claude Code usage. Same core approach (spawns `claude`, runs `/usage`, parses terminal output) but as a Swift/SwiftUI GUI instead of a CLI/library.

# ai-quota

Unified CLI and Python API for monitoring quota usage across AI coding assistants: **Claude Code**, **Gemini CLI**, and **Codex**.

## Features

- **Multi-provider** — Query Claude Code, Gemini, and Codex from one tool
- **CLI + Python API** — Use from the terminal or import in scripts
- **Caching** — Atomic JSON cache for instant reads; refresh on demand
- **Multiple output formats** — Plain text, JSON, Slack-friendly markdown, pretty progress bars
- **Reset countdowns** — Shows when quota resets in relative and absolute time
- **Token tracking** — Codex provider reads local SQLite DB for token counts
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

# Run with coverage
pytest --cov=src

# Lint & format
ruff check src tests
ruff format src tests
```

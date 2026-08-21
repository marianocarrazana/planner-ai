# Planner AI

Multi-agent terminal UI: several independent proposer agents inspect the workspace in parallel (each on a model you pick), then a separate consensus agent reconciles their outputs into one plan, answer, or improvements list. Plan mode archives `plan.md` under `.planner-ai/`; Ask mode archives a Q&A answer; Improve mode archives a prioritized improvements list. It plans, answers, and audits; it does not execute.

It is both **multi-model** (Claude, Grok, GPT, Gemini, etc) and **multi-agent** (one agent per proposer, plus a consensus agent—not a single agent that fans out to several models).

## Requirements

- Python ≥ 3.14
- [uv](https://docs.astral.sh/uv/)

## Install and run

### From this directory (development)

```bash
cd planner-ai
uv sync
uv run planner
```

Or:

```bash
uv run python -m planner_ai
```

### Install as a tool (any project)

From PyPI:

```bash
uv tool install planner-ai
# or: pip install planner-ai
```

From this package directory (development):

```bash
uv tool install .
```

Then from any project you want to plan:

```bash
cd ~/code/my-app
planner
```

Both the Bun and Python CLIs expose the same console name `planner`. If both are on your `PATH`, whichever comes first wins. Prefer one install at a time, or call the Python app explicitly with `uv run --directory /path/to/planner-ai planner`.

## Authentication

On first run the TUI opens **Auth** when no real provider is connected. Configure at least one provider; empty Enter cancels a token editor:

- **ChatGPT for Codex** — browser login uses your eligible ChatGPT subscription. Device-code login (beta) is available for remote/headless environments and may need to be enabled in ChatGPT security or workspace settings.
- **Claude Code OAuth token** — run `claude setup-token`, then paste (Team / Pro / Max subscription)
- **Cursor API key** — from [Cursor Dashboard → Integrations](https://cursor.com/dashboard/integrations)
- **Codex API key** — optional fallback from [OpenAI API keys](https://platform.openai.com/api-keys); this uses standard API billing rather than ChatGPT subscription access.

Browser login tries to open the system browser and also leaves the sign-in URL visible in the TUI. Device-code login shows a verification URL and one-time code. A successful ChatGPT login replaces any planner-ai Codex API-key configuration.

Claude, Cursor, and optional Codex API-key values are saved under the OS user config directory (same path and JSON shape as the TypeScript app):

- macOS: `~/Library/Application Support/planner-ai/config.json`
- Linux: `~/.config/planner-ai/config.json` (or `$XDG_CONFIG_HOME/planner-ai`)
- Windows: `%APPDATA%\planner-ai\config.json`

Never commit tokens or put them in `.env`. The app does not log credential values.

ChatGPT credentials are not stored in planner-ai's config. Codex stores and refreshes them in its standard shared cache or OS keyring, so planner-ai, Codex CLI, and the Codex IDE extension use the same active session. Disconnecting Codex or resetting authentication signs all of those local Codex clients out.

Providers without authentication are omitted; if none are connected, mock providers are used. With real providers present, mocks appear only when `includeMocks` is enabled (press `m` on Proposers/Consensus).

If authentication fails during a run, the error screen offers **`r`** to remove a failing key or disconnect a failing ChatGPT session and return to Auth (or **`q`** to quit). To clear all credentials, including the shared Codex session, without launching the TUI:

```bash
uv run planner --reset-auth
# or, if installed as a tool:
planner --reset-auth
```

## What it does

- Plans/asks/improves against the folder you launched the CLI in (`cwd`)
- Runs several proposer agents in parallel, each on a different model (one failure does not cancel the others)
- Runs a separate consensus agent (on its own model) to reconcile those proposals
- **Plan mode:** archives the consensus plan under `.planner-ai/plan-…/` (does **not** write cwd `plan.md`)
- **Ask mode:** same multi-agent proposer + consensus flow with Q&A prompts; archives under `.planner-ai/ask-…/`
- **Improve mode:** same flow with audit prompts; required free-text scope (suggestion chips: Last commits / Commits in this branch / Whole repo); agents interpret the scope themselves; archives under `.planner-ai/improve-…/`

## TUI

Fullscreen alternate-screen UI with tabs:

| Tab | Shortcut | What it does |
| --- | --- | --- |
| **Plan** | `Ctrl+1` | Plan/Ask/Improve toggle, enter a goal, question, or scope, watch proposals / consensus, browse the result |
| **Proposers** | `Ctrl+2` | Pick proposer models (multi) — Claude / Cursor / Codex / Mock |
| **Consensus** | `Ctrl+3` | Pick the consensus model (single) |
| **Auth** | `Ctrl+4` | Connect ChatGPT or manage Claude / Cursor / Codex credentials |
| **History** | `Ctrl+5` | Browse past successful runs archived under `.planner-ai/` |

You can also click the tab labels. On Models: click a row or use `↑↓` / `PgUp`/`PgDn`, `Space` toggle/choose, `/` filter, `m` toggle mocks, `c` continues to Plan.

Startup opens **Auth** if no real provider is authenticated, else **Proposers** if there is no saved selection, else **Plan**.

## How it works

1. You provide a goal (Plan), question (Ask), or scope (Improve) on the Plan tab.
2. Each proposer agent inspects the current working directory (read-only) with its own tools and proposes independently.
3. A consensus agent inspects the workspace and reconciles those proposals into one plan, answer, or improvements list.
4. All modes archive under `.planner-ai/` (`plan.md`, `answer.md`, or `improvements.md`).

```mermaid
flowchart LR
  Goal[Goal question or scope] --> Proposers[Proposer agents in parallel]
  Proposers --> Consensus[Consensus agent]
  Consensus --> Plan[plan.md answer.md or improvements.md archive]
```

## Output

`.planner-ai/plan-…/plan.md` (Plan mode) is the artifact meant for a later execution step. This tool produces the plan; it does not run it.

Each successful run is archived under `.planner-ai/`:

```
.planner-ai/
  plan-2026-08-13T16-48-00/
    anthropic-claude-sonnet-4-5-output.md
    plan.md
  ask-2026-08-13T16-49-00/
    cursor-composer-2.5-output.md
    answer.md
  improve-2026-08-13T16-50-00/
    cursor-composer-2.5-output.md
    improvements.md
```

- Plan runs: `plan-{YYYY-MM-DDTHH-MM-SS}/` with per-model `*-output.md` and consensus `plan.md`
- Ask runs: `ask-{YYYY-MM-DDTHH-MM-SS}/` with per-model `*-output.md` and consensus `answer.md`
- Improve runs: `improve-{YYYY-MM-DDTHH-MM-SS}/` with per-model `*-output.md` and consensus `improvements.md`
- Collision dirs: `plan-{ts}-2`, `plan-{ts}-3`, …
- History lists all kinds newest-first (by timestamp, not full dirname)

Archives written by the TypeScript app remain readable.

## Development

```bash
cd planner-ai
uv sync
uv run planner              # TUI (plans cwd)
uv run planner --reset-auth
uv run pytest
uv run ruff check src tests
```

Plan another folder without installing:

```bash
cd ~/code/my-app
uv run --directory /path/to/planner-ai/planner-ai planner
```

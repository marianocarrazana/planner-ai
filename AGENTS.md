# AGENTS.md (Python package)

Agent notes for the Python port under `planner-ai/`. Product rules match the repo-root [`AGENTS.md`](../AGENTS.md); commands and stack below are Python-specific.

## Project

Terminal UI (Textual) that asks several models for a plan or answer in parallel, reconciles via a consensus model, and either writes `plan.md` (Plan mode) or returns a Q&A answer (Ask mode). It plans/answers; it does not execute.

## Stack

- Runtime: Python ≥ 3.14 + `uv`
- UI: Textual
- Providers: `claude-agent-sdk`, `cursor-sdk`, `openai-codex`, plus mock fallbacks
- Language: Python; package layout under `src/planner_ai/`

## Commands

From `planner-ai/`:

```bash
uv sync
uv run planner                    # TUI (plans cwd)
uv run python -m planner_ai       # same
uv run planner --reset-auth       # clear stored credentials; does not start TUI
uv run pytest
uv run ruff check src tests
```

Console script name is `planner` (same as the TypeScript bin). Prefer one install on `PATH` at a time.

## Layout

```
src/planner_ai/
  cli.py                 # --reset-auth + Textual app
  app.py                 # tabs + orchestration
  config.py              # OS user config (tokens + model selection)
  workspace.py           # get_workspace_cwd() = Path.cwd().resolve()
  write_plan.py          # writes cwd plan.md (Plan mode only)
  write_run_archive.py   # archives run under .planner-ai/
  read_run_archive.py    # list/read archived runs for History tab
  ui/                    # Textual screens/widgets
  pipeline/              # run_pipeline + types
  providers/             # anthropic, cursor, codex, mock, models, prompts, resolve
tests/
```

## Conventions

- Keep changes scoped; match existing naming and widget style.
- Provider surface: `ModelProvider.propose` and `ConsensusProvider.reconcile` in `providers/types.py`.
- Wire new models through `providers/models.py` and `providers/resolve.py`.
- Prompts live in `providers/prompts.py`; keep them read-only over the workspace. Plan vs Ask via `ProviderCallOptions.mode`.
- Credentials belong only in the OS config path from `config.py` — never commit tokens, never log them.
- Sanitize pasted tokens with `sanitize_token` before persist/use.
- Plan mode: always-current artifact is `plan.md` in the workspace cwd.
- Ask mode: Plan tab toggle; same multi-proposer + consensus flow with Q&A prompts; does not write cwd `plan.md`.
- Each successful run is archived under `.planner-ai/`:
  - Plan: `plan-{YYYY-MM-DDTHH-MM-SS}/` with per-model `*-output.md` and `plan.md`
  - Ask: `ask-{YYYY-MM-DDTHH-MM-SS}/` with per-model `*-output.md` and `answer.md`
  - History lists both kinds newest-first (sorted by timestamp, not full dirname).

## Boundaries

**Always**

- Run `uv run ruff check src tests` and focused `uv run pytest` after meaningful edits.
- Preserve alternate-screen TUI behavior and existing keyboard shortcuts unless changing them intentionally.
- Keep archive layout and config JSON keys compatible with the TypeScript app.

**Ask first**

- Adding a new LLM provider or changing auth/credential storage.
- Renaming or relocating `plan.md` / workspace resolution.
- Introducing a package manager other than `uv`.

**Never**

- Commit `.env`, credentials, or real API keys.
- Execute the generated plan as part of this tool’s job.
- Add SQL/drizzle migrations or a `drizzle/` folder.
- Clear user credentials except via `--reset-auth` / Auth tab flows the user chose.

## Commits

When asked to commit, use multiline messages — one simple line per change, each prefixed with `Add`, `Update`, `Delete`, `Refactor`, `Fix`, or `Style`. Do not include reasons (`for`, `clarifying`, etc.).

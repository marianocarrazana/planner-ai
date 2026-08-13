# AGENTS.md

## Project

Terminal UI (OpenTUI + React) that asks several models for a plan in parallel, reconciles via a consensus model, and writes `plan.md` in the launch directory. It plans; it does not execute.

## Stack

- Runtime: Bun ≥ 1.2 (`type: "module"`)
- UI: `@opentui/core` + `@opentui/react` (JSX import source is `@opentui/react`, not `react`)
- Providers: Anthropic Claude Agent SDK, Cursor SDK, plus mock fallbacks
- Language: TypeScript strict; ESM imports use `.js` extensions (`./foo.js`)

## Commands

```bash
bun install
bun run dev          # TUI (plans cwd)
bun start            # same as dev
bun run typecheck    # tsc --noEmit
bun start -- --reset-auth   # clear stored credentials
```

There is no test suite yet. Prefer `bun run typecheck` after meaningful edits.

## Layout

```
src/
  cli.tsx           # entry, --reset-auth, OpenTUI renderer
  app.tsx           # tabs + orchestration
  config.ts         # OS user config (tokens + model selection)
  workspace.ts      # getWorkspaceCwd() = process.cwd()
  writePlan.ts         # writes cwd plan.md
  writeRunArchive.ts   # archives run under .planner-ai/
  components/          # TUI screens/widgets
  pipeline/            # runPipeline + types
  providers/           # anthropic, cursor, mock, models, prompts, resolve
```

## Conventions

- Keep changes scoped; match existing naming and component style.
- Provider surface: `ModelProvider.propose` and `ConsensusProvider.reconcile` in `providers/types.ts`.
- Wire new models through `providers/models.ts` and `providers/resolve.ts`.
- Prompts live in `providers/prompts.ts`; keep them read-only over the workspace.
- Credentials belong only in the OS config path from `config.ts` — never commit tokens, never log them.
- Sanitize pasted tokens with `sanitizeToken` before persist/use.
- Always-current artifact is `plan.md` in the workspace cwd.
- Each successful run is also archived under `.planner-ai/plan-{YYYY-MM-DDTHH-MM-SS}/` with per-model `*-output.md` files and a copy of `plan.md` (lexicographic sort newest-last; reverse for newest-first).

## Boundaries

**Always**

- Run `bun run typecheck` when touching shared types or providers.
- Preserve alternate-screen TUI behavior and existing keyboard shortcuts unless changing them intentionally.

**Ask first**

- Adding a new LLM provider or changing auth/credential storage.
- Renaming or relocating `plan.md` / workspace resolution.
- Introducing a package manager other than Bun, or adding a test runner.

**Never**

- Commit `.env`, credentials, or real API keys.
- Execute the generated plan as part of this tool’s job.
- Add SQL/drizzle migrations or a `drizzle/` folder (out of scope for this repo).
- Never remove the user credentials (bun start -- --reset-auth)

## Commits

When asked to commit, use multiline messages — one simple line per change, each prefixed with `Add`, `Update`, `Delete`, `Refactor`, `Fix`, or `Style`. Do not include reasons (`for`, `clarifying`, etc.).

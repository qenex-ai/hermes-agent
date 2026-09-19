# Hermes Agent - Development Guide

Instructions for AI coding assistants and developers working on the hermes-agent codebase.
This root file is loaded **every session** — keep it short. Area-specific rules live in
`<dir>/AGENTS.md` (~8k chars each; see routing table). Deep rubric, footprint ladder, facade
rules, and full testing reference:
`website/docs/developer-guide/agents-reference-extended.md`. Checkout paths and Cloud bootstrap:
`docs/cloud-agent-and-checkout.md`.

**Never give up on the right solution.**

## First commands

```bash
source .venv/bin/activate   # or: source venv/bin/activate
scripts/run_tests.sh tests/<area>/              # scope tests (never bare pytest)
scripts/run_tests.sh tests/foo.py -k test_name
ruff check .                                    # blocking Python lint (CI)
npm run check                                   # when touching .ts/.tsx (all workspaces)
```

Touching only Python → scoped `scripts/run_tests.sh`. Touching JS/TS → also `npm run check`
(CI classifier may skip Python on JS-only PRs). Full suite is ~39k tests — do not run unless needed.

## What Hermes Is

Hermes is a personal AI agent that runs the same agent core across a CLI, a messaging
gateway (Telegram, Discord, Slack, ~20 platforms), a TUI, and an Electron desktop app. It
learns across sessions (memory + skills), delegates to subagents, runs scheduled jobs, and
drives a real terminal and browser. It is extended primarily through **plugins and skills**,
not by growing the core.

Two invariants shape almost every design decision:

- **Per-conversation prompt caching is sacred.** Do not mutate past context, swap toolsets,
  reload memories, or rebuild the system prompt mid-conversation (exception: context compression).
  Slash commands that change skills/tools/memory default to **next session** with opt-in `--now`
  (`/skills install --now` is canonical).
- **The core is a narrow waist.** New capability: extend → CLI+skill → `check_fn` tool → plugin
  → MCP catalog → core tool (last). Session-scoped UI tools use **toolsets**, not process env
  (see extended reference).

Before a large change or triage decision, read the **Contribution Rubric** and **Footprint
Ladder** in `website/docs/developer-guide/agents-reference-extended.md`.

## Development Environment

`scripts/run_tests.sh` probes `.venv`, then `venv`, then `$HOME/.hermes/hermes-agent/venv`.

Cursor Cloud: `scripts/cloud-agent-install.sh` (idempotent `uv sync --frozen`, Node via nvm,
web dashboard build). Per-boot servers → environment `start` or tmux, not the install script.

**Checkout paths:** `/workspace` (Cloud) or `/root/hermes-src` (deploy) — same tree; see
`docs/cloud-agent-and-checkout.md`.

### Build & lint (verified invocations)

```bash
uv sync --frozen --python "$(cat .python-version 2>/dev/null || echo 3.11)" \
  --extra all --extra dev --extra anthropic --extra mistral --extra fal \
  --extra modal --extra daytona --extra hindsight --extra parallel-web
source .venv/bin/activate

scripts/run_tests.sh
scripts/run_tests.sh tests/hermes_cli/test_foo.py -k test_name

uv tool install ruff ty
ruff check .
python scripts/check_compat_pointers.py

npm ci
npm run check
npm run build --workspace web    # bundle for `hermes dashboard`
```

## Project Structure

Load-bearing entry points (filesystem is canonical):

```
run_agent.py, model_tools.py, toolsets.py, cli.py, hermes_state.py, hermes_constants.py
agent/          turn loop, providers, memory, compression
hermes_cli/     CLI, setup, config, web_routers/, updater
tools/          registry + environments/
gateway/        run.py facade, platforms/
plugins/ skills/ optional-skills/
ui-tui/ tui_gateway/ apps/desktop/ web/
tests/          mirrors source tree under tests/<top-level>/
scripts/        run_tests.sh, ci/, check_compat_pointers.py
website/        Docusaurus + developer-guide/
```

**User state:** `get_hermes_home()` → `config.yaml`, `.env` (secrets only), `logs/`. Never
hardcode `~/.hermes` in code (`display_hermes_home()` for user-facing paths).

**Facade + siblings:** god files split into `<stem>.py` + `<stem>_<topic>.py`; patch where
production imports from the facade. Details: extended reference.

## Code shape (summary)

- No argv-substring process detection — use `gateway.status.looks_like_gateway_command_line`
  and `hermes_cli.update_cmd._hermes_holder_subcommand`.
- No `if/elif` ladders ≥4 branches on a name — table dispatch (`_SLASH_DISPATCH`, gateway
  `_command_handler_table`).
- **Compat:** do not import `PLUGIN-COMPAT` paths in-tree; CI runs
  `scripts/check_compat_pointers.py`. Blocks exist for external plugins until the scheduled
  revert; import defining modules only.
- TypeScript: nanostores, thin route roots, interfaces for public props — see extended reference.

**Dependencies:** upper bounds on all deps; run `uv lock` after `pyproject.toml` edits.

## Testing (summary)

**Always** `scripts/run_tests.sh` — CI parity (`HERMES_HOME` temp dir, UTC, per-file subprocesses).

| Without wrapper | With wrapper |
| --- | --- |
| Real API keys / `~/.hermes` | Isolated env |
| Shared interpreter | One subprocess per test file |

- Mirror source tree under `tests/`. No change-detector or source-regex tests.
- OS-specific behavior → `@pytest.mark.linux_only` / `macos_only` / `windows_only` (never fake
  `sys.platform`). JS config assertions → vitest in `tests-js/`, not Python.

Full policy: `website/docs/developer-guide/agents-reference-extended.md`.

## Pitfalls

- **Full suite** takes a long time — always scope by directory or file.
- **Bare pytest** with keys set → false green/red vs CI.
- **JS-only PR** may skip Python tests in CI; run `npm run check` locally.
- **Profile tests** must set `HERMES_HOME` and mock `Path.home()` together.
- **Squash merge** stale branches → silent reverts; rebase onto `main` before merge.
- **Prompt cache:** no mid-conversation system prompt or toolset churn except compression.

## Routing Table — working in X → read X/AGENTS.md

| Area | Read | Covers |
|---|---|---|
| `run_agent.py`, `agent/` | `agent/AGENTS.md` | Turn loop, caching, compression, aux resolution |
| `cli.py`, `hermes_cli/`, `main.py` | `hermes_cli/AGENTS.md` | Slash registry, config loaders, update, profiles |
| `gateway/` | `gateway/AGENTS.md` | Adapters, guards, streaming, scoped secrets |
| `tools/`, `toolsets.py`, `model_tools.py` | `tools/AGENTS.md` | Registry, toolsets, delegation |
| `plugins/`, `hermes_cli/plugins*.py` | `plugins/AGENTS.md` | Plugin kinds, in-tree policy |
| `tui_gateway/`, `ui-tui/` | `tui_gateway/AGENTS.md` | JSON-RPC, TUI slash flow |
| `web/`, `hermes_cli/web_routers/` | `web/AGENTS.md` | Dashboard embeds real TUI |
| `apps/desktop/` | `apps/desktop/AGENTS.md`, `apps/desktop/src/AGENTS.md` | Desktop shell, Bot Mode |
| `skills/`, `optional-skills/`, `agent/curator*.py` | `skills/AGENTS.md` | SKILL frontmatter, curator |
| `cron/`, kanban | `cron/AGENTS.md` | Scheduler, kanban dispatcher |
| New messaging adapter | `gateway/platforms/ADDING_A_PLATFORM.md` | Adapter checklist |

Long-form: `website/docs/developer-guide/` (agent-loop, gateway-internals, tools-runtime, …).

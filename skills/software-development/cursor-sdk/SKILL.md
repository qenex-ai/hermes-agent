---
name: cursor-sdk
description: "Run Cursor SDK agents with prompt, send, or resume."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Cursor, SDK, Cloud-Agent, Automation]
    related_skills: [claude-code, codex, opencode, hermes-agent]
    category: software-development
---

# Cursor SDK Skill

Drive Cursor agents from Hermes via `hermes cursor-sdk`, which shells to the
TypeScript `@cursor/sdk` runner. This skill does not add a Hermes model tool.
Use it when the user wants Cursor's local or cloud agent runtime, not Hermes'
own coding loop.

## When to Use

- The user asks to run a Cursor SDK agent, `Agent.prompt`, `Agent.create`, or `Agent.resume`
- A one-shot Cursor task (`prompt`) or a durable multi-turn Cursor session (`send` / `resume`)
- Cloud agents that should open a PR against a GitHub repo URL

Do not use this for ordinary Hermes coding work. Prefer Hermes `terminal`,
`read_file`, `patch`, and `search_files` unless the user asked for Cursor.

## Prerequisites

- Node.js >= 22.13 and npm (the runner lives at `scripts/cursor-sdk`)
- `CURSOR_API_KEY` in `.env` (user key or team service account). Never put it in `config.yaml`
- Explicit runtime on every call: `--local` or `--cloud`. Omitting both silently defaults the SDK to local
- Cloud: a GitHub repo URL the key can access; CI should keep `skip_reviewer_request` (the CLI default)

## How to Run

Invoke through `terminal`. The Python CLI is a thin wrapper; SDK calls stay in TypeScript.

```
terminal(command="hermes cursor-sdk prompt 'Summarize src/auth.ts' --local --cwd /path/to/repo")
```

```
terminal(command="hermes cursor-sdk send 'Find the bug in src/auth.ts' --local --follow-up 'Write a regression test'")
```

```
terminal(command="hermes cursor-sdk resume bc-abc123 'Also update the changelog' --cloud --repo https://github.com/org/repo")
```

## Quick Reference

| Command | SDK pattern | Notes |
|---|---|---|
| `hermes cursor-sdk prompt TEXT --local\|--cloud` | `Agent.prompt` | One-shot; SDK disposes |
| `hermes cursor-sdk send TEXT --local\|--cloud [--follow-up TEXT]` | `Agent.create` + `send` | Streams, `wait()`, dispose in `finally` |
| `hermes cursor-sdk resume ID TEXT --local\|--cloud` | `Agent.resume` | Re-pass `--mcp-json`; inline MCP is not persisted |
| `hermes cursor-sdk get ID --local\|--cloud` | `Agent.get` | Inspect |
| `hermes cursor-sdk get-run RUN --cloud --agent-id ID` | `Agent.getRun` | A `bc-` ID is an **agent** ID, not a run ID |
| `hermes cursor-sdk list --local\|--cloud` | `Agent.list` | |

Exit codes: `0` finished, `1` startup / `CursorAgentError`, `2` `result.status === "error"`. Retry only when the log says `retryable=true`.

Default model is `composer-2`. Local `settingSources` default to `[]`. Cloud CI sets `skipReviewerRequest: true`.

## Procedure

1. Confirm `CURSOR_API_KEY` is set. Pass it through; the wrapper injects `apiKey` explicitly
2. Pick the pattern: one-shot → `prompt`; streaming or follow-ups in this process → `send`; continue later → `resume`
3. Pass `--local --cwd …` or `--cloud --repo …` (and `--ref` if not `main`)
4. For durable `send`, add `--follow-up` so the second `agent.send` shares conversation state
5. On resume, pass `--mcp-json` again if the original run used inline MCP servers
6. Log lines include `agent=` and `run=` immediately after `send()` — keep those IDs for `get` / `get-run`

## Pitfalls

- Never omit both `--local` and `--cloud`
- Do not pass a `bc-` ID to `get-run`
- Do not blindly retry failed cloud runs (`isRetryable` is authoritative)
- `Agent.prompt` cannot do a follow-up; use `send` or `resume`
- Inline `mcpServers` die across process boundaries unless re-passed on resume

## Verification

```
terminal(command="hermes cursor-sdk --help")
terminal(command="hermes cursor-sdk prompt --help")
```

A missing key should exit 1 with a `CURSOR_API_KEY` message, not start a silent local agent.

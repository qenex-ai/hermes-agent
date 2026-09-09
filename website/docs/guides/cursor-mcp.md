---
sidebar_position: 7
title: "Use Hermes MCP in Cursor IDE"
description: "Wire this checkout into Cursor as MCP tools — not as an external ACP agent"
---

# Use Hermes MCP in Cursor IDE

Cursor already has a coding agent. This repository wires Hermes into Cursor as **MCP tools**, not as a second external agent over ACP.

Project config: [`.cursor/mcp.json`](https://github.com/qenex-ai/hermes-agent/blob/main/.cursor/mcp.json). Merge new servers into that file; do not wipe other `mcpServers` entries. A GitHub-oriented copy of this guide lives at [`docs/cursor-mcp.md`](https://github.com/qenex-ai/hermes-agent/blob/main/docs/cursor-mcp.md).

## MCP vs ACP

| What | Command | Role | Use in Cursor? |
|------|---------|------|----------------|
| **Hermes MCP server** | `hermes mcp serve` | Cursor is the agent; Hermes exposes **messaging-bridge tools** | **Yes** |
| **Hermes ACP server** | `hermes acp` | Hermes *is* the coding agent inside an ACP host | **No** — use Zed, JetBrains, or VS Code ACP Client |
| **Cursor `agent acp`** | Cursor CLI | Cursor *is* an ACP **server** for other editors | Opposite direction from `hermes acp` |

`hermes mcp serve` is not “full Hermes coding agent inside Cursor.” It does not run Hermes’ file, terminal, or delegate toolset in the IDE. The tools are the channel bridge (`conversations_list`, `messages_read`, `messages_send`, …) described in [Running Hermes as an MCP server](/user-guide/features/mcp#running-hermes-as-an-mcp-server). For Hermes-in-editor, see [ACP Host Integration](/user-guide/features/acp).

## `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "hermes": {
      "command": "hermes",
      "args": ["mcp", "serve"]
    },
    "qenex": {
      "url": "https://mcp.qenex.ai"
    },
    "supabase": {
      "url": "https://mcp.supabase.com/mcp?project_ref=tmsvyuxaiozmcxdaaqeu&features=docs%2Caccount%2Cdatabase%2Cdebugging%2Cdevelopment%2Cfunctions%2Cbranching"
    }
  }
}
```

**`hermes` (stdio):** `hermes` on `PATH` is the committed default. GUI Cursor often has a thin PATH — if the server fails to start, point `command` at `$HOME/.hermes/hermes-agent/venv/bin/hermes` (Windows: `%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes.exe`). This QENEX fork has no separate absolute venv.

The Hermes gateway is optional for reads and required for `messages_send`.

**`qenex` (HTTP):** Cursor usually prompts for **OAuth** on first connect. QENEX publishes OAuth protected-resource metadata at `https://mcp.qenex.ai` (scope `mcp`). Do not put bearer tokens in the project file.

### QENEX URL path

A live probe of `mcp.qenex.ai` (2026-09-09):

- Origin and `/sse` accept MCP traffic (`401` + `WWW-Authenticate: Bearer` until authed)
- `/mcp` returns `404`

The committed `url` is therefore `https://mcp.qenex.ai`, matching the OAuth `resource` field. If ops later mounts Streamable HTTP at `/mcp`, update `.cursor/mcp.json` to `https://mcp.qenex.ai/mcp`.

**`supabase` (HTTP):** hosted Supabase MCP, scoped to the QENEX `qenex` project (`tmsvyuxaiozmcxdaaqeu`). Cursor prompts for **OAuth** on first connect. Do not put a personal access token in the project file. After authorizing, restart the session so tools load.

Vendor skills live in [`.agents/skills/`](https://github.com/qenex-ai/hermes-agent/blob/main/.agents/skills) (`npx skills add supabase/agent-skills -a cursor -y`, pinned by `skills-lock.json`).

## Enable

1. Install Hermes so `hermes doctor` works in a login shell.
2. Open this repo in Cursor. Project MCP servers load from `.cursor/mcp.json`.
3. **Cursor Settings → MCP**: enable `hermes`, `qenex`, and `supabase`; complete QENEX and Supabase OAuth if prompted.
4. Confirm messaging-bridge tools appear — not an ACP Hermes session panel. Confirm Supabase tools such as `list_tables` appear for project `tmsvyuxaiozmcxdaaqeu`.

## See also

- [MCP Integration](/user-guide/features/mcp)
- [ACP Host Integration](/user-guide/features/acp)
- [Use MCP with Hermes](/guides/use-mcp-with-hermes) (Hermes as an MCP *client*)

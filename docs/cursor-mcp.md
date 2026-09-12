# Cursor IDE: Hermes as MCP, not ACP

Cursor already has a coding agent. This fork wires Hermes into Cursor as **MCP tools**, not as a second external agent over ACP.

Project config lives in [`.cursor/mcp.json`](../.cursor/mcp.json). Merge new servers into that file; do not replace other `mcpServers` entries.

## MCP vs ACP (do not mix these up)

| What | Command / surface | Role | Use in Cursor? |
|------|-------------------|------|----------------|
| **Hermes MCP server** | `hermes mcp serve` | Cursor is the agent; Hermes exposes **messaging-bridge tools** (list conversations, read history, send on Telegram/Discord/Slack, …) | **Yes** — this is the Cursor integration |
| **Hermes ACP server** | `hermes acp` / `hermes-acp` | Hermes *is* the coding agent; an ACP host (Zed, JetBrains, VS Code ACP Client, Buzz) owns the editor UI | **No** — those hosts, not Cursor |
| **Cursor `agent acp`** | Cursor CLI | Cursor *is* the ACP **server** so other editors can drive Cursor | Opposite direction from `hermes acp` |

`hermes mcp serve` is **not** “full Hermes coding agent inside Cursor.” It does not run Hermes’ file/terminal/delegate toolset in the IDE. It exposes the channel-bridge tools documented in the [MCP feature page](../website/docs/user-guide/features/mcp.md#running-hermes-as-an-mcp-server). For the full Hermes-in-editor loop, use ACP in Zed / JetBrains / VS Code — see [ACP Host Integration](../website/docs/user-guide/features/acp.md).

## Servers in `.cursor/mcp.json`

### `hermes` (stdio)

Default: `hermes` on `PATH`.

```json
"hermes": {
  "command": "hermes",
  "args": ["mcp", "serve"]
}
```

If Cursor cannot find `hermes` (GUI apps often inherit a thin PATH), point at the install venv — the same path the [MCP feature docs](../website/docs/user-guide/features/mcp.md) use:

```json
"hermes": {
  "command": "/home/YOU/.hermes/hermes-agent/venv/bin/hermes",
  "args": ["mcp", "serve"]
}
```

Replace `YOU` with your username. On this QENEX fork there is no separate absolute venv; the managed install is still `$HOME/.hermes/hermes-agent/venv/bin/hermes` (or `%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes.exe` on native Windows). Keep the PATH form in the committed file; override locally only when needed.

The gateway does **not** need to be running for reads. It **does** need to be running for `messages_send`.

### `qenex` (HTTP MCP)

```json
"qenex": {
  "url": "https://mcp.qenex.ai"
}
```

Cursor will typically prompt for **OAuth** on first connect. QENEX advertises itself as an OAuth protected resource (`/.well-known/oauth-protected-resource` → `resource: https://mcp.qenex.ai`, scope `mcp`).

**Path check (ops):** a live probe of `mcp.qenex.ai` (2026-09-09) found:

- `POST https://mcp.qenex.ai/` and `POST https://mcp.qenex.ai/sse` → `401` with `WWW-Authenticate: Bearer` (MCP endpoint present; auth required)
- `POST https://mcp.qenex.ai/mcp` → `404 Not Found`

The committed URL is therefore the **origin**, which matches the OAuth resource metadata — not `/mcp`. If ops later mounts Streamable HTTP at `/mcp`, change the `url` in `.cursor/mcp.json` to `https://mcp.qenex.ai/mcp`.

Do not put bearer tokens in `mcp.json`. Let Cursor’s OAuth flow (or your user-level Cursor MCP headers) supply credentials.

### `supabase` (HTTP MCP)

```json
"supabase": {
  "url": "https://mcp.supabase.com/mcp?project_ref=tmsvyuxaiozmcxdaaqeu&features=docs%2Caccount%2Cdatabase%2Cdebugging%2Cdevelopment%2Cfunctions%2Cbranching"
}
```

Hosted Supabase MCP, **project-scoped** to the QENEX `qenex` project (`tmsvyuxaiozmcxdaaqeu`). Feature groups match the dashboard export: docs, account, database, debugging, development, functions, branching. Storage stays off (Supabase default). Cursor prompts for **OAuth** on first connect — do not put a PAT in the project file.

Project-scoped mode disables account-management tools even if `account` is listed in `features`. Restart the Cursor session after authorizing so tools load.

Vendor agent skills: `npx skills add supabase/agent-skills -a cursor -y` installs `supabase` and `supabase-postgres-best-practices` into `.agents/skills/` (pinned by `skills-lock.json`).

### `pipedrive` (HTTP MCP)

```json
"pipedrive": {
  "url": "https://mcp.pipedrive.ai/mcp"
}
```

Official Pipedrive CRM MCP. Cursor prompts for **OAuth** on first connect. Tools inherit your Pipedrive role and visibility. Do not put API tokens in the project file.

**Path check (ops):** a live probe of `mcp.pipedrive.ai` (2026-09-10) found:

- `POST https://mcp.pipedrive.ai/mcp` → `401` with `WWW-Authenticate: Bearer` (MCP endpoint present; auth required). OAuth `resource` is `https://mcp.pipedrive.ai/mcp`
- `POST https://mcp.pipedrive.ai/` and `POST https://mcp.pipedrive.ai/sse` → `301` to `pipedrive.com` (not MCP)

The committed URL is therefore **`https://mcp.pipedrive.ai/mcp`**, matching the OAuth resource metadata. Hermes-as-client: `hermes mcp` → install catalog entry `pipedrive`.

**Claude.ai / Claude Desktop:** [Pipedrive MCP for Claude](https://support.pipedrive.com/en/article/mcp-claude) — Customize → Connectors → Add custom connector, name `Pipedrive MCP BETA`, connection `https://mcp.pipedrive.ai/mcp`. Enable “load all available tools” in the connector if Claude truncates the tool list. ChatGPT: [Pipedrive MCP for ChatGPT](https://support.pipedrive.com/en/article/mcp-chatgpt).

### `sourcegraph` (HTTP MCP)

```json
"sourcegraph": {
  "url": "https://sourcegraph.com/.api/mcp"
}
```

Official Sourcegraph Cloud MCP ([docs](https://sourcegraph.com/docs/api/mcp)). Cursor prompts for **OAuth** on first connect (Dynamic Client Registration, scope `mcp`). Do not put access tokens in the project file. Token auth is optional for local/user config: set `SOURCEGRAPH_ACCESS_TOKEN` and add `"Authorization": "token ${env:SOURCEGRAPH_ACCESS_TOKEN}"`.

**Path check (ops):** a live probe of `sourcegraph.com` (2026-09-11) found:

- `POST https://sourcegraph.com/.api/mcp` → `401` with `WWW-Authenticate: Bearer resource_metadata="https://sourcegraph.com/.well-known/oauth-protected-resource/.api/mcp", scope="mcp"` (MCP endpoint present; auth required). OAuth `resource` is `https://sourcegraph.com/.api/mcp`
- `POST https://sourcegraph.com/` → HTML (not MCP)
- `POST https://sourcegraph.com/sse` → `404`

The committed URL is therefore **`https://sourcegraph.com/.api/mcp`**, matching the OAuth resource metadata. Hermes-as-client: `hermes mcp` → install catalog entry `sourcegraph`. Self-hosted instances use `https://<your-instance>/.api/mcp`. GitHub Copilot CLI (optional, not configured here): `copilot mcp add --transport http sourcegraph https://sourcegraph.com/.api/mcp` then `/mcp auth sourcegraph`.

## Enable in Cursor

1. Install Hermes so `hermes` is on your shell PATH (`hermes doctor` should work).
2. Open this repo in Cursor. Project MCP servers load from `.cursor/mcp.json`.
3. **Cursor Settings → MCP**: enable `hermes`, `qenex`, `supabase`, `pipedrive`, and `sourcegraph`. Approve QENEX, Supabase, Pipedrive, and Sourcegraph OAuth if prompted.
4. Confirm `hermes` tools such as `conversations_list` / `messages_send` appear — not the Hermes ACP session UI. Confirm Supabase tools such as `list_tables` / `execute_sql` appear for project `tmsvyuxaiozmcxdaaqeu`. Confirm Pipedrive deal/contact tools appear after OAuth. Confirm Sourcegraph tools such as `keyword_search` / `nls_search` appear after OAuth.

User-level Cursor MCP config (`~/.cursor/mcp.json`) is fine for personal servers; keep fork defaults in the project file so the checkout is self-describing.

## See also

- [Running Hermes as an MCP server](../website/docs/user-guide/features/mcp.md#running-hermes-as-an-mcp-server)
- [ACP Host Integration](../website/docs/user-guide/features/acp.md) (Zed, JetBrains, VS Code — not Cursor)
- [Use MCP with Hermes](../website/docs/guides/use-mcp-with-hermes.md) (Hermes *as* an MCP *client*)

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

## Enable in Cursor

1. Install Hermes so `hermes` is on your shell PATH (`hermes doctor` should work).
2. Open this repo in Cursor. Project MCP servers load from `.cursor/mcp.json`.
3. **Cursor Settings → MCP**: enable `hermes` and `qenex`. Approve QENEX OAuth if prompted.
4. Confirm `hermes` tools such as `conversations_list` / `messages_send` appear — not the Hermes ACP session UI.

User-level Cursor MCP config (`~/.cursor/mcp.json`) is fine for personal servers; keep fork defaults in the project file so the checkout is self-describing.

## See also

- [Running Hermes as an MCP server](../website/docs/user-guide/features/mcp.md#running-hermes-as-an-mcp-server)
- [ACP Host Integration](../website/docs/user-guide/features/acp.md) (Zed, JetBrains, VS Code — not Cursor)
- [Use MCP with Hermes](../website/docs/guides/use-mcp-with-hermes.md) (Hermes *as* an MCP *client*)

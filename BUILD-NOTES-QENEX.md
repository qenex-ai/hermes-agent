# Building hermes-agent on node-london (2026-08-11)

Verified working: `Hermes Agent v0.20.0 (2026.8.3)`, Python 3.11.14, venv 117 MB.

## The three traps

1. **`pip install .` FAILS BY DESIGN.** The build backend raises
   `RuntimeError: Building wheels or sdists for hermes-agent is not supported.`
   This is deliberate, not a broken package. Use `uv sync`.

2. **The system `uv` (0.9.13, /usr/local/bin/uv) CANNOT PARSE THIS LOCK.** It
   fails with `invalid type: boolean false, expected a timestamp string` at
   `[options]`. The project uses newer uv features — a relative
   `exclude-newer = "14 days"` and boolean `exclude-newer-package = { h2 = false, ... }`.
   Needs uv >= ~0.12.

   Do NOT upgrade /usr/local/bin/uv in place: other things on this box use it.
   An isolated newer uv lives at /opt/hermes-uv (a venv with `pip install uv`,
   currently 0.12.3).

3. **MCP servers go under `mcp_servers`, NOT `mcp.servers`.** The two differ by
   one character and belong to two different products. `mcp.servers` is
   **OpenClaw's** schema; Hermes reads only the flat `mcp_servers` key
   (`tools/mcp_tool.py:5092` — `config.get("mcp_servers")`). The migration
   script states the mapping outright: it reads `mcp.servers` from OpenClaw and
   writes `mcp_servers` to Hermes
   (`optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py:2255,2325`).

   Hand-writing the config in the OpenClaw shape costs hours, because **every
   error message is accurate and every one of them reads like a different bug**:

   - `hermes mcp test qenex` → `Auth: none` then HTTP 401
   - `hermes mcp reauth qenex` → `Server 'qenex' is not configured for OAuth (auth=None)`
   - `errors.log` → `failed initial authentication, parking until credentials change`

   All three are true statements about `mcp_servers.qenex`, which held only
   `{url, enabled: false}`. The 401 was never a rejected token — it was an
   **unauthenticated request**, because no header was ever attached. Replaying
   the same token by hand returns HTTP 200, which proves the credential and says
   nothing about whether Hermes sends it. Do not debug the credential; check
   which key the value is under first:

       python3 -c "import yaml;print(sorted((yaml.safe_load(open('/root/.hermes/config.yaml')).get('mcp_servers') or {})))"

   Also: `transport:` is only ever compared against `"sse"` (`mcp_tool.py:3057`).
   Streamable HTTP is what you get by default when `url` is set, so
   `transport: streamable-http` is an unvalidated no-op string that merely looks
   like a setting. Omit it.

## Reproduce

    git clone https://github.com/qenex-ai/hermes-agent.git /root/hermes-src
    python3 -m venv /opt/hermes-uv && /opt/hermes-uv/bin/pip install -q uv
    /opt/hermes-uv/bin/uv sync --frozen
    /opt/hermes-uv/bin/uv run hermes --version

The upstream `curl | bash` installer was deliberately NOT used: it also pulls
Node.js, ffmpeg and ripgrep, and this host runs at ~92% disk. `uv sync` gets the
Python agent alone.

## Footprint vs OpenClaw

    hermes-agent   222 MB source + 117 MB venv
    openclaw       11 GB tree + 4.8 GB cache (was 25 GB before the 2026-08-11 cleanup)

## Capabilities confirmed present

`mcp` (manage MCP servers AND run Hermes as an MCP server), `skills`, `tools`,
`serve` (headless backend), `chat`, `config`.

## Verified working (2026-08-11)

- **Inference**: local Ollama, `qwen3-coder-next:latest` (262,144 ctx). Hermes
  enforces a **>= 64K context floor** — `qwen2.5:7b` reports 32K and is rejected.
  Zero-Cost path proven end to end: session `20260811_232513_515f52` recorded
  `HERMES_OLLAMA_OK` in `~/.hermes/state.db`, billing provider `custom`.
- **MCP**: `hermes mcp test qenex` → connected in 552 ms, **180 tools** discovered
  over `https://mcp.qenex.ai`. Hermes redacts the header itself (`Bear***wIW4`).
- **MCP in the AGENT path** (a different code path from `mcp test` — it goes
  through `register_mcp_servers` with trust/filter/lazy layers). Confirmed from
  `~/.hermes/logs/agent.log` during a real `-z` run:
  `MCP: registered 180 tool(s) from 1 server(s)`.

  **Tools are exposed to the model as `mcp__<server>__<tool>`**, e.g.
  `mcp__qenex__qenex_cache_stats`, NOT `qenex_cache_stats`. A prompt naming the
  unprefixed tool gets a truthful "I have no such tool" and reads exactly like a
  wiring failure. Check `agent.log` for the `registered N tool(s)` line before
  believing the model about its own capabilities.

  Note `-z/--oneshot` runs with `args.command is None`, which
  `_should_background_mcp_startup` (`hermes_cli/main.py:10831`) routes to
  BACKGROUND discovery with no join — unlike the TUI path, which does a bounded
  join before the first tool snapshot. Registration won the race in every
  observed run, but it is a race; if a oneshot ever reports no tools, check the
  timestamps in agent.log before changing config.

## `hermes serve` — measured, and DELIBERATELY not made a unit yet

Works headless: `hermes serve --port 9119 --host 127.0.0.1 --skip-build` →
`HERMES_BACKEND_READY port=9119`.

**`--skip-build` is mandatory on this host.** Without it, `serve` runs an npm
build of the web UI. There is no pre-built `web/dist` in the tree, and build
churn on a 92%-full disk is the exact failure that filled it under OpenClaw.
Skipping it costs the browser UI and keeps the JSON-RPC/WebSocket backend, which
is all a headless agent needs.

Auth, probed rather than assumed (`curl` on loopback, no credentials):

    POST /api/rpc  tools/list                    -> 401 {"detail":"Unauthorized"}
    POST /api/rpc  tools/call qenex_terminal_secure -> 401 {"detail":"Unauthorized"}
    GET  /api/status                             -> 200 (unauthenticated)

So unauthenticated tool invocation is refused. But note `/api/status` reports
`"auth_required": false, "auth_providers": []` — the 401 comes from a local
session-token check, **not** from a configured auth provider. Do not read
"auth_required: false" as "this port is open"; do not read the 401 as "a
password is configured". Neither is true.

**No unit was created, on purpose.** Nothing consumes 9119 today: the desktop
app is not installed here, claw.qenex.ai is still served by OpenClaw, and both
the `hermes` CLI and `cron.enabled` work without `serve`. An always-on backend
holding 180 live tools — including `qenex_terminal_secure`, `qenex_mail_send`,
`qenex_wise_transfer_propose` — is a standing surface with no current consumer.
Create the unit when there IS one, and configure a password auth provider first.

If/when that happens: `ExecStart` must be the venv console script, **not**
`uv run` (which re-resolves the lockfile on every start — network plus cache
writes on a full disk — and inserts a parent between systemd and the main PID).
Do **not** set `ExecStop=hermes serve --stop`: per its own `--help` that stops
*all* Hermes server processes, so a `systemctl restart` would also kill any
interactive session. Plain SIGTERM to the main PID is right. `OnFailure=` goes
under `[Unit]`.

## NOT yet done
- No cutover from OpenClaw. OpenClaw is still serving claw.qenex.ai and its
  sync/deploy timers are DISABLED (2026-08-11) to stop the pnpm-store churn.
- The Pinata-hosted agent "commercialing humanized"
  (/commercialing-humanized-xvhlj3av, engine: hermes) is a SEPARATE deployment —
  its skills are IPFS-CID-addressed. Decide whether this local build replaces it,
  feeds it, or is unrelated, before decommissioning anything.

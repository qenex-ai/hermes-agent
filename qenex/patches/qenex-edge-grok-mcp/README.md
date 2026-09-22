# Grok.com MCP connector patch (qenex-edge)

Apply on London `/opt/qenex` (git remote `root/qenex-edge`), then restart MCP:

```bash
sudo systemctl restart qenex-mcp-server.service
```

## Changes

1. **`qenex_mcp_server.py`** — allow OAuth DCR redirect hostnames under `grok.com` and `x.ai` (xAI Grok custom connectors use cloud HTTPS callbacks, not loopback).
2. **`qenex_core/mcp/transport.py`** — add `POST/GET/DELETE /mcp` alias (Grok CLI examples use `/mcp`); emit `WWW-Authenticate` with `resource_metadata` for MCP OAuth discovery.

Canonical policy + tests: `qenex/mcp_oauth_redirect.py` and `tests/qenex/test_mcp_oauth_redirect.py` in this repo.

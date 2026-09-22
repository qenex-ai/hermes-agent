#!/usr/bin/env bash
# Apply Grok.com MCP OAuth + /mcp route patch on London /opt/qenex (root/qenex-edge).
# Run ON the London host as a user who can edit /opt/qenex and restart qenex-mcp-server.
set -euo pipefail

REPO="${1:-/opt/qenex}"
PATCH_DIR="$(cd "$(dirname "$0")/../qenex/patches/qenex-edge-grok-mcp" && pwd)"

if [[ ! -f "$REPO/qenex_mcp_server.py" ]]; then
  echo "Expected qenex-edge checkout at $REPO" >&2
  exit 1
fi

echo "Review snippets in $PATCH_DIR and merge into:"
echo "  $REPO/qenex_mcp_server.py"
echo "  $REPO/qenex_core/mcp/transport.py"
echo "Then: sudo systemctl restart qenex-mcp-server.service"
echo "Verify: curl -sS -o /dev/null -w '%{http_code}\n' -X POST https://mcp.qenex.ai/mcp"

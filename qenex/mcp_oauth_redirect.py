# Copyright (c) 2026 QENEX LTD. All Rights Reserved.
"""OAuth redirect URI policy for mcp.qenex.ai (shared with qenex-edge).

Kept in hermes-agent so redirect rules are testable without the London checkout.
Production copy lives in root/qenex-edge ``qenex_mcp_server.py`` — keep in sync.
"""

from __future__ import annotations

from urllib.parse import urlparse

# Exact hostnames (loopback, single-tenant agents, Cursor cloud callback).
ALLOWED_REDIRECT_HOSTS: frozenset[str] = frozenset(
    {
        "claude.ai",
        "localhost",
        "127.0.0.1",
        "commercialing-humanized-9513.agents.nousresearch.com",
        "xvhlj3av.agents.pinata.cloud",
        "www.cursor.com",
    }
)

# Single-tenant xAI surfaces — allow apex + subdomains (not multi-tenant SaaS).
ALLOWED_REDIRECT_DOMAIN_SUFFIXES: tuple[str, ...] = (
    "grok.com",
    "x.ai",
)

# Custom URI schemes (Cursor desktop DCR).
ALLOWED_REDIRECT_SCHEMES: frozenset[str] = frozenset({"cursor"})


def redirect_host_allowed(hostname: str | None) -> bool:
    if not hostname:
        return False
    host = hostname.lower()
    if host in ALLOWED_REDIRECT_HOSTS:
        return True
    for suffix in ALLOWED_REDIRECT_DOMAIN_SUFFIXES:
        if host == suffix or host.endswith(f".{suffix}"):
            return True
    return False


def redirect_uri_allowed(uri: str) -> bool:
    """True iff *uri* may be used as an OAuth redirect (DCR + /authorize)."""
    try:
        parsed = urlparse(uri)
    except Exception:
        return False
    scheme = (parsed.scheme or "").lower()
    if scheme in ALLOWED_REDIRECT_SCHEMES:
        return True
    if scheme not in ("http", "https"):
        return False
    return redirect_host_allowed(parsed.hostname)

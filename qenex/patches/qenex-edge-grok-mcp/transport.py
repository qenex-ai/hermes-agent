# Copyright (c) 2026 QENEX LTD. All Rights Reserved.
# Drop-in replacement for qenex_core/mcp/transport.py (Grok /mcp + OAuth PRM).
# Copy to /opt/qenex/qenex_core/mcp/transport.py on London, then restart qenex-mcp-server.

from __future__ import annotations

import json
import logging

from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Mount, Route

from qenex_core.mcp.kernel import _mcp_server

log = logging.getLogger("QENEX.MCP.transport")

_MCP_ORIGIN = "https://mcp.qenex.ai"
_OAUTH_PRM = f"{_MCP_ORIGIN}/.well-known/oauth-protected-resource"

_session_manager: StreamableHTTPSessionManager | None = None


def get_session_manager() -> StreamableHTTPSessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = StreamableHTTPSessionManager(
            app=_mcp_server,
            stateless=True,
        )
    return _session_manager


def _unauthorized() -> Response:
    return Response(
        content=json.dumps({"detail": "Unauthorized — Bearer token required"}),
        status_code=401,
        media_type="application/json",
        headers={
            "WWW-Authenticate": (
                f'Bearer realm="mcp.qenex.ai", '
                f'resource_metadata="{_OAUTH_PRM}", scope="mcp"'
            ),
        },
    )


class _ASGIEndpoint:
    def __init__(self, handler):
        self._handler = handler

    async def __call__(self, scope, receive, send):
        await self._handler(scope, receive, send)


def build_mcp_server() -> Starlette:
    sse = SseServerTransport("/messages/")
    mgr = get_session_manager()

    async def handle_root_endpoint(scope, receive, send):
        from qenex_core.mcp.tools import _AUTH_FN, _request_user

        user = await _AUTH_FN(scope) if _AUTH_FN else None
        if user is None:
            await _unauthorized()(scope, receive, send)
            return
        _request_user.set(user)
        await mgr.handle_request(scope, receive, send)

    async def handle_sse_endpoint(scope, receive, send):
        from qenex_core.mcp.tools import _AUTH_FN, _request_user

        user = await _AUTH_FN(scope) if _AUTH_FN else None
        if user is None:
            await _unauthorized()(scope, receive, send)
            return
        _request_user.set(user)

        if scope["method"] == "GET":
            async with sse.connect_sse(scope, receive, send) as streams:
                await _mcp_server.run(
                    streams[0], streams[1], _mcp_server.create_initialization_options()
                )
        else:
            await mgr.handle_request(scope, receive, send)

    async def handle_post(scope, receive, send):
        from qenex_core.mcp.tools import _AUTH_FN, _request_user

        user = await _AUTH_FN(scope) if _AUTH_FN else None
        if user is None:
            await _unauthorized()(scope, receive, send)
            return
        _request_user.set(user)
        await sse.handle_post_message(scope, receive, send)

    return Starlette(
        routes=[
            Route(
                "/",
                endpoint=_ASGIEndpoint(handle_root_endpoint),
                methods=["GET", "POST", "DELETE"],
            ),
            Route(
                "/mcp",
                endpoint=_ASGIEndpoint(handle_root_endpoint),
                methods=["GET", "POST", "DELETE"],
            ),
            Route(
                "/sse",
                endpoint=_ASGIEndpoint(handle_sse_endpoint),
                methods=["GET", "POST", "DELETE"],
            ),
            Mount("/messages", app=handle_post),
        ]
    )

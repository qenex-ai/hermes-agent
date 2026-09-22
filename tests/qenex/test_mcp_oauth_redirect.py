"""OAuth redirect policy for mcp.qenex.ai — Grok.com / x.ai connector support."""

from qenex.mcp_oauth_redirect import redirect_uri_allowed


def test_grok_and_xai_redirect_hosts_allowed():
    assert redirect_uri_allowed("https://grok.com/connectors/oauth/callback")
    assert redirect_uri_allowed("https://www.grok.com/foo")
    assert redirect_uri_allowed("https://accounts.x.ai/oauth/callback")
    assert redirect_uri_allowed("https://console.x.ai/oauth/callback")


def test_loopback_and_cursor_still_allowed():
    assert redirect_uri_allowed("http://127.0.0.1:8765/callback")
    assert redirect_uri_allowed("http://localhost:8765/callback")
    assert redirect_uri_allowed("cursor://anysphere.cursor-mcp/oauth/callback")
    assert redirect_uri_allowed("https://www.cursor.com/agents/mcp/oauth/callback")


def test_unrelated_hosts_rejected():
    assert not redirect_uri_allowed("https://evil.example.com/cb")
    assert not redirect_uri_allowed("https://agents.nousresearch.com/cb")

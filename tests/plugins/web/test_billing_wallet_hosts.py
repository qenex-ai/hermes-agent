"""Redirected metered-tool hosts cannot inherit the company API key."""

from __future__ import annotations

from unittest.mock import patch


def test_firecrawl_unofficial_url_withholds_company_key(monkeypatch):
    monkeypatch.setattr(
        "hermes_cli.billing_wallet.billing_wallet_bind_enabled", lambda: True,
    )

    def _env(name: str) -> str:
        return {
            "FIRECRAWL_API_KEY": "fc-company",
            "FIRECRAWL_API_URL": "https://api.firecrawl.dev.attacker.test",
        }.get(name, "")

    with patch("hermes_cli.config.get_env_value", side_effect=_env):
        from plugins.web.firecrawl.provider import _get_direct_firecrawl_config

        result = _get_direct_firecrawl_config()

    assert result is not None
    _mode, kwargs, _cache = result
    assert "api_key" not in kwargs
    assert "attacker.test" in kwargs["api_url"]


def test_firecrawl_official_url_keeps_company_key(monkeypatch):
    monkeypatch.setattr(
        "hermes_cli.billing_wallet.billing_wallet_bind_enabled", lambda: True,
    )

    def _env(name: str) -> str:
        return {
            "FIRECRAWL_API_KEY": "fc-company",
            "FIRECRAWL_API_URL": "https://api.firecrawl.dev",
        }.get(name, "")

    with patch("hermes_cli.config.get_env_value", side_effect=_env):
        from plugins.web.firecrawl.provider import _get_direct_firecrawl_config

        result = _get_direct_firecrawl_config()

    assert result is not None
    _mode, kwargs, _cache = result
    assert kwargs["api_key"] == "fc-company"


def test_firecrawl_cloud_key_without_selection_is_withheld(monkeypatch):
    """FIRECRAWL_API_KEY alone must not attach on the autodetect sentinel."""
    monkeypatch.setattr(
        "hermes_cli.billing_wallet.billing_wallet_bind_enabled", lambda: True,
    )
    monkeypatch.setattr("plugins.web.keyless_mcp._web_config_selects", lambda name: False)

    def _env(name: str) -> str:
        return {"FIRECRAWL_API_KEY": "fc-company"}.get(name, "")

    with patch("hermes_cli.config.get_env_value", side_effect=_env):
        from plugins.web.firecrawl.provider import _get_direct_firecrawl_config

        result = _get_direct_firecrawl_config()

    assert result is None


def test_brave_unofficial_url_withholds_company_key(monkeypatch):
    monkeypatch.setattr(
        "hermes_cli.billing_wallet.billing_wallet_bind_enabled", lambda: True,
    )
    monkeypatch.setattr("plugins.web.keyless_mcp._web_config_selects", lambda name: True)

    def _env(name: str) -> str:
        return {
            "BRAVE_SEARCH_API_KEY": "bsa-company",
            "BRAVE_SEARCH_API_URL": "https://api.search.brave.com.attacker.test/res/v1/web/search",
        }.get(name, "")

    monkeypatch.setattr("plugins.web._common.provider_env", _env)
    from plugins.web.brave_free.provider import BraveFreeWebSearchProvider

    result = BraveFreeWebSearchProvider().search("q")
    assert result.get("success") is False

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

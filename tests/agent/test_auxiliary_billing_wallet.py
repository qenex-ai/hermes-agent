"""Aux OpenRouter discovery cannot spend the company wallet on a named-vendor hop."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.auxiliary_client import _try_discovery_chain, _try_openrouter


def test_named_vendor_aux_openrouter_does_not_attach_company_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-company-or")
    monkeypatch.setattr(
        "hermes_cli.billing_wallet.billing_wallet_bind_enabled", lambda: True,
    )
    with patch("agent.auxiliary_client._select_pool_entry", return_value=(False, None)), \
         patch("agent.auxiliary_client.OpenAI") as mock_openai:
        client, model = _try_openrouter(requested="anthropic")

    assert client is None
    assert model is None
    mock_openai.assert_not_called()


def test_named_vendor_aux_openrouter_uses_requestor_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-company-or")
    monkeypatch.setattr(
        "hermes_cli.billing_wallet.billing_wallet_bind_enabled", lambda: True,
    )
    with patch("agent.auxiliary_client._select_pool_entry", return_value=(False, None)), \
         patch("agent.auxiliary_client.OpenAI") as mock_openai:
        mock_client = MagicMock(name="attacker_client")
        mock_openai.return_value = mock_client
        client, _model = _try_openrouter(
            requested="anthropic", explicit_api_key="sk-attacker",
        )

    assert client is mock_client
    assert mock_openai.call_args.kwargs["api_key"] == "sk-attacker"


def test_explicit_openrouter_aux_still_uses_company_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-company-or")
    monkeypatch.setattr(
        "hermes_cli.billing_wallet.billing_wallet_bind_enabled", lambda: True,
    )
    with patch("agent.auxiliary_client._select_pool_entry", return_value=(False, None)), \
         patch("agent.auxiliary_client.OpenAI") as mock_openai:
        mock_client = MagicMock(name="company_client")
        mock_openai.return_value = mock_client
        client, _model = _try_openrouter()

    assert client is mock_client
    assert mock_openai.call_args.kwargs["api_key"] == "sk-company-or"


def test_discovery_chain_named_vendor_skips_company_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-company-or")
    monkeypatch.setattr(
        "hermes_cli.billing_wallet.billing_wallet_bind_enabled", lambda: True,
    )
    with patch("agent.auxiliary_client._select_pool_entry", return_value=(False, None)), \
         patch("agent.auxiliary_client._try_nous", return_value=(None, None)), \
         patch("agent.auxiliary_client._try_custom_endpoint", return_value=(None, None)), \
         patch("agent.auxiliary_client._resolve_api_key_provider", return_value=(None, None)), \
         patch("agent.auxiliary_client.OpenAI") as mock_openai:
        client, model, label = _try_discovery_chain(requested="anthropic")

    assert client is None
    assert model is None
    assert label == ""
    mock_openai.assert_not_called()

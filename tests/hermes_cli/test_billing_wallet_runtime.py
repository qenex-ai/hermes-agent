"""Last-rung OpenRouter cannot spend the company wallet on a named-vendor request."""

from __future__ import annotations

import pytest

from hermes_cli import runtime_provider as rp
from hermes_cli.auth import AuthError


@pytest.fixture
def bind_on(monkeypatch):
    monkeypatch.setattr("hermes_cli.billing_wallet.billing_wallet_bind_enabled", lambda: True)


def test_named_vendor_fallthrough_does_not_attach_company_openrouter_key(monkeypatch, bind_on):
    monkeypatch.setattr(rp, "_get_model_config", lambda: {"provider": "openai-codex"})
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-company-or")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("CUSTOM_BASE_URL", raising=False)

    with pytest.raises(AuthError) as exc:
        rp._resolve_openrouter_runtime(requested_provider="openai-codex")
    assert exc.value.code == "billing_hijack_blocked"
    assert "sk-company-or" not in str(exc.value)


def test_named_vendor_fallthrough_uses_requestor_key(monkeypatch, bind_on):
    monkeypatch.setattr(rp, "_get_model_config", lambda: {"provider": "openai-codex"})
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-company-or")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("CUSTOM_BASE_URL", raising=False)

    resolved = rp._resolve_openrouter_runtime(
        requested_provider="openai-codex", explicit_api_key="sk-attacker",
    )
    assert resolved["api_key"] == "sk-attacker"
    assert "openrouter.ai" in (resolved["base_url"] or "")


def test_explicit_openrouter_still_uses_company_key(monkeypatch, bind_on):
    monkeypatch.setattr(rp, "_get_model_config", lambda: {"provider": "openrouter"})
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-company-or")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("CUSTOM_BASE_URL", raising=False)

    resolved = rp._resolve_openrouter_runtime(requested_provider="openrouter")
    assert resolved["api_key"] == "sk-company-or"


def test_operator_selected_openrouter_without_key_still_resolves(monkeypatch, bind_on):
    """Empty-key OpenRouter after an explicit selection is a loud 401, not a hijack block."""
    monkeypatch.setattr(rp, "_get_model_config", lambda: {"provider": "openrouter"})
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("CUSTOM_BASE_URL", raising=False)

    resolved = rp._resolve_openrouter_runtime(requested_provider="openrouter")
    assert resolved["provider"] == "openrouter"
    assert not (resolved["api_key"] or "").strip()

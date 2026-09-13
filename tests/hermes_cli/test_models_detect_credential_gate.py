"""Auto-detection must never hand the user a provider they hold no credentials for.

Regression for the "accidental provider" class: ``/model <name>`` on provider A, where the name is
only known to provider B (static catalog or OpenRouter), used to switch the session to B even when
B had no key — an immediate 401 for most vendors, and for OpenRouter (whose runtime resolves with an
empty key instead of raising) a silent switch onto a metered aggregator.
"""

from __future__ import annotations

import pytest

from hermes_cli import models


@pytest.fixture
def no_live_catalog(monkeypatch):
    monkeypatch.setattr(models, "cached_provider_model_ids", lambda provider, **_: [])
    monkeypatch.setattr(models, "_find_openrouter_slug", lambda name: f"vendor/{name}")


@pytest.fixture
def authed(monkeypatch):
    """Pin which providers count as authenticated; everything else has no credentials."""
    from hermes_cli import models_detect

    granted: set[str] = set()
    monkeypatch.setattr(models_detect, "provider_has_credentials", lambda p: p in granted)
    return granted


class TestNoCredentialsNoSwitch:
    def test_openrouter_only_model_stays_when_no_openrouter_key(self, no_live_catalog, authed):
        assert models.detect_provider_for_model("some-model-only-openrouter-has", "deepseek") is None

    def test_openrouter_key_is_not_consent_to_remap(self, no_live_catalog, authed, monkeypatch):
        """Holding OPENROUTER_API_KEY must not auto-hop a native session onto OpenRouter."""
        monkeypatch.setattr("hermes_cli.billing_wallet.billing_wallet_bind_enabled", lambda: True)
        authed.add("openrouter")
        assert models.detect_provider_for_model("some-model-only-openrouter-has", "deepseek") is None

    def test_explicit_openrouter_prefix_still_remaps_with_key(self, no_live_catalog, authed, monkeypatch):
        monkeypatch.setattr("hermes_cli.billing_wallet.billing_wallet_bind_enabled", lambda: True)
        authed.add("openrouter")
        got = models.detect_provider_for_model("openrouter/some-model-only-openrouter-has", "deepseek")
        assert got is not None and got[0] == "openrouter"

    def test_static_vendor_match_requires_that_vendors_credentials(self, no_live_catalog, authed, monkeypatch):
        monkeypatch.setattr(models, "detect_static_provider_for_model", lambda n, c: ("anthropic", n))
        assert models.detect_provider_for_model("claude-something", "deepseek") is None
        authed.add("anthropic")
        assert models.detect_provider_for_model("claude-something", "deepseek") == ("anthropic", "claude-something")

    def test_explicitly_named_provider_is_not_gated(self, no_live_catalog, authed, monkeypatch):
        """``/model nous`` names the provider: hand it back so the credential step can prompt/fail
        loudly instead of silently ignoring the request."""
        monkeypatch.setattr(models, "detect_static_provider_for_model", lambda n, c: ("nous", "hermes-4-405b"))
        assert models.detect_provider_for_model("nous", "deepseek") == ("nous", "hermes-4-405b")

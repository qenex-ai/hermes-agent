"""Company wallet must not pay for a metered-aggregator hijack.

Contract: a hop onto OpenRouter (or another metered aggregator) that the operator did not
select cannot attach the company key. A requestor-supplied key still attaches — they pay.
"""

from __future__ import annotations

import json

from hermes_cli.billing_wallet import (
    allow_aggregator_auto_switch,
    aggregator_api_key_candidates,
    company_openrouter_wallet_eligible,
    record_billing_hijack,
)


class TestCompanyOpenRouterWalletEligible:
    def test_operator_selected_openrouter_may_use_company_key(self):
        assert company_openrouter_wallet_eligible(requested="openrouter", bind_enabled=True)
        assert company_openrouter_wallet_eligible(requested="auto", bind_enabled=True)
        assert company_openrouter_wallet_eligible(requested="custom", bind_enabled=True)

    def test_named_vendor_fallthrough_cannot_use_company_key(self):
        assert not company_openrouter_wallet_eligible(requested="deepseek", bind_enabled=True)
        assert not company_openrouter_wallet_eligible(requested="anthropic", bind_enabled=True)
        assert not company_openrouter_wallet_eligible(requested="openai-codex", bind_enabled=True)

    def test_bind_disabled_restores_historical_fallthrough(self):
        assert company_openrouter_wallet_eligible(requested="deepseek", bind_enabled=False)


class TestAggregatorAutoSwitch:
    def test_openrouter_key_is_not_consent_to_hop(self):
        assert not allow_aggregator_auto_switch(
            model_name="some-model-only-openrouter-has",
            current_provider="deepseek",
            target_provider="openrouter",
            bind_enabled=True,
        )

    def test_explicit_openrouter_prefix_still_hops(self):
        assert allow_aggregator_auto_switch(
            model_name="openrouter/vendor/model",
            current_provider="deepseek",
            target_provider="openrouter",
            bind_enabled=True,
        )

    def test_already_on_openrouter_may_remap_slug(self):
        assert allow_aggregator_auto_switch(
            model_name="vendor/model",
            current_provider="openrouter",
            target_provider="openrouter",
            bind_enabled=True,
        )

    def test_native_vendor_hop_is_unchanged(self):
        assert allow_aggregator_auto_switch(
            model_name="claude-something",
            current_provider="deepseek",
            target_provider="anthropic",
            bind_enabled=True,
        )


class TestAttackerPays:
    def test_ineligible_request_uses_only_requestor_key(self):
        keys = aggregator_api_key_candidates(
            requested="deepseek",
            explicit_api_key="sk-attacker",
            company_keys=["sk-company-or", "sk-company-openai"],
            bind_enabled=True,
        )
        assert keys == ["sk-attacker"]
        assert "sk-company-or" not in keys

    def test_ineligible_request_without_requestor_key_is_empty(self):
        keys = aggregator_api_key_candidates(
            requested="deepseek",
            explicit_api_key="",
            company_keys=["sk-company-or"],
            bind_enabled=True,
        )
        assert keys == []

    def test_eligible_request_still_prefers_explicit_then_company(self):
        keys = aggregator_api_key_candidates(
            requested="openrouter",
            explicit_api_key="sk-session",
            company_keys=["sk-company-or"],
            bind_enabled=True,
        )
        assert keys[0] == "sk-session"
        assert "sk-company-or" in keys


def test_hijack_audit_writes_jsonl_without_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr("hermes_constants.get_hermes_home", lambda: tmp_path)
    record_billing_hijack(
        reason="openrouter-last-rung",
        requested="deepseek",
        destination="https://openrouter.ai/api/v1",
        requestor_paid=True,
    )
    log = tmp_path / "logs" / "billing-hijack.jsonl"
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert rec["reason"] == "openrouter-last-rung"
    assert rec["requested"] == "deepseek"
    assert rec["requestor_paid"] is True
    assert "sk-" not in log.read_text(encoding="utf-8")

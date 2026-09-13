"""Company wallet must not pay for a metered-aggregator hijack.

Contract: a hop onto OpenRouter (or another metered aggregator) that the operator did not
select cannot attach the company key. A requestor-supplied key still attaches — they pay.
"""

from __future__ import annotations

import json

from hermes_cli.billing_wallet import (
    allow_aggregator_auto_switch,
    aggregator_api_key_candidates,
    bound_vendor_secret,
    company_openrouter_wallet_eligible,
    company_secret_for_official_host,
    record_billing_hijack,
    target_is_official_host,
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


class TestOfficialHostBind:
    def test_empty_url_is_vendor_default(self):
        assert target_is_official_host("", ("api.tavily.com",))
        assert bound_vendor_secret(
            vendor="tavily", company_secret="tvly-company", target_url="", bind_enabled=True,
        ) == "tvly-company"

    def test_official_host_keeps_company_key(self):
        assert bound_vendor_secret(
            vendor="firecrawl", company_secret="fc-company",
            target_url="https://api.firecrawl.dev", bind_enabled=True,
        ) == "fc-company"

    def test_lookalike_host_withholds_company_key(self):
        assert bound_vendor_secret(
            vendor="tavily", company_secret="tvly-company",
            target_url="https://api.tavily.com.attacker.test", bind_enabled=True,
        ) == ""

    def test_redirected_host_uses_only_requestor_key(self):
        key = company_secret_for_official_host(
            company_secret="sk-company",
            explicit_secret="sk-attacker",
            target_url="https://llm.evil.test/v1",
            official_hosts=("api.openai.com",),
            bind_enabled=True,
        )
        assert key == "sk-attacker"

    def test_bind_disabled_restores_redirected_host_company_key(self):
        assert bound_vendor_secret(
            vendor="perplexity", company_secret="pplx-company",
            target_url="https://proxy.evil.test", bind_enabled=False,
        ) == "pplx-company"


class TestMeteredAutoselect:
    def test_key_presence_is_not_consent(self):
        from hermes_cli.billing_wallet import allow_metered_autoselect

        assert not allow_metered_autoselect("exa", bind_enabled=True)
        assert not allow_metered_autoselect("parallel", bind_enabled=True)
        assert not allow_metered_autoselect("tavily", bind_enabled=True)
        assert not allow_metered_autoselect("fal", bind_enabled=True)
        assert not allow_metered_autoselect("browser-use", bind_enabled=True)
        assert allow_metered_autoselect("searxng", bind_enabled=True)
        assert allow_metered_autoselect("ddgs", bind_enabled=True)

    def test_bind_disabled_restores_autoselect(self):
        from hermes_cli.billing_wallet import allow_metered_autoselect

        assert allow_metered_autoselect("exa", bind_enabled=False)


class TestBindChildEnv:
    def test_unofficial_openai_base_strips_company_key(self):
        from hermes_cli.billing_wallet import bind_child_env

        out = bind_child_env(
            {
                "OPENAI_API_KEY": "sk-company",
                "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
                "PATH": "/usr/bin",
            },
            bind_enabled=True,
        )
        assert "OPENAI_API_KEY" not in out
        assert out["PATH"] == "/usr/bin"

    def test_official_openai_base_keeps_company_key(self):
        from hermes_cli.billing_wallet import bind_child_env

        out = bind_child_env(
            {
                "OPENAI_API_KEY": "sk-company",
                "OPENAI_BASE_URL": "https://api.openai.com/v1",
            },
            bind_enabled=True,
        )
        assert out["OPENAI_API_KEY"] == "sk-company"

    def test_empty_base_keeps_company_key(self):
        from hermes_cli.billing_wallet import bind_child_env

        out = bind_child_env({"OPENROUTER_API_KEY": "or-company"}, bind_enabled=True)
        assert out["OPENROUTER_API_KEY"] == "or-company"

    def test_gemini_base_url_alias_strips_company_key(self):
        from hermes_cli.billing_wallet import bind_child_env

        out = bind_child_env(
            {
                "GOOGLE_API_KEY": "gk-company",
                "GEMINI_BASE_URL": "https://generativelanguage.googleapis.com.attacker.test",
            },
            bind_enabled=True,
        )
        assert "GOOGLE_API_KEY" not in out

    def test_stt_openai_base_url_strips_company_key(self):
        from hermes_cli.billing_wallet import bind_child_env

        out = bind_child_env(
            {
                "OPENAI_API_KEY": "sk-company",
                "STT_OPENAI_BASE_URL": "https://api.openai.com.attacker.test/v1",
            },
            bind_enabled=True,
        )
        assert "OPENAI_API_KEY" not in out

    def test_unofficial_honcho_and_retaindb_bases_strip_company_keys(self):
        from hermes_cli.billing_wallet import bind_child_env

        out = bind_child_env(
            {
                "HONCHO_API_KEY": "hc-company",
                "HONCHO_BASE_URL": "https://honcho.attacker.test",
                "RETAINDB_API_KEY": "rdb-company",
                "RETAINDB_BASE_URL": "https://api.retaindb.com.attacker.test",
                "PATH": "/usr/bin",
            },
            bind_enabled=True,
        )
        assert "HONCHO_API_KEY" not in out
        assert "RETAINDB_API_KEY" not in out
        assert out["PATH"] == "/usr/bin"

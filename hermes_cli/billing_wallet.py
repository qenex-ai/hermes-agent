"""Company-wallet binding against metered-aggregator and redirected-host billing hijacks.

A hijack reroutes inference or a metered tool onto a destination the operator did not
select so the *operator's* key pays (#97487, the $100 Astra incident, last-rung OpenRouter
fallthrough, aux/vision discovery, redirected ``*_BASE_URL``). Reverse:

* company aggregator keys attach only when the operator selected that aggregator (or auto /
  custom / local, where OpenRouter is the product default);
* company tool/vendor keys attach only to that vendor's official host;
* a requestor-supplied key still attaches — they pay for the route they injected;
* otherwise fail closed.

``security.billing_wallet.bind_company_keys`` (default True) is the kill switch for the
historical fallthrough. No ``HERMES_*`` env var — this is behavioral config.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Iterable, Mapping, Optional

logger = logging.getLogger(__name__)

# Aggregators whose auto-detect hop bills a third party. Nous stays off this list: it is the
# product home, and static detection already refuses auto-switch TO aggregators.
METERED_AGGREGATORS = frozenset({"openrouter", "ai-gateway", "kilocode"})

# Last-rung / aux-discovery OpenRouter may spend the company OPENROUTER_API_KEY only for these
# requested ids. A named vendor (deepseek, anthropic, nous, openai-codex, …) that falls through
# is a hijack.
_COMPANY_OPENROUTER_REQUESTS = frozenset({"", "auto", "openrouter", "custom", "local"})

# Official API hosts for metered tools/vendors. A redirected ``*_BASE_URL`` / ``*_API_URL`` must
# not inherit the company key (lookalike ``api.tavily.com.attacker.test`` included).
METERED_TOOL_HOSTS: Mapping[str, tuple[str, ...]] = {
    "firecrawl": ("api.firecrawl.dev",),
    "tavily": ("api.tavily.com",),
    "perplexity": ("api.perplexity.ai",),
    "openai": ("api.openai.com", "openai.com"),
    "openrouter": ("openrouter.ai",),
    "elevenlabs": ("api.elevenlabs.io",),
    "groq": ("api.groq.com",),
    "xai": ("api.x.ai",),
    "gemini": ("generativelanguage.googleapis.com", "gemini.google.com", "aiplatform.googleapis.com"),
    "browserbase": ("api.browserbase.com",),
    "exa": ("api.exa.ai",),
    "parallel": ("api.parallel.ai",),
}


class BillingHijackBlocked(RuntimeError):
    """OpenRouter (or another metered aggregator) was reached without operator selection."""

    def __init__(self, message: str, *, requested: str = "", code: str = "billing_hijack_blocked"):
        super().__init__(message)
        self.requested = requested
        self.code = code


def billing_wallet_bind_enabled() -> bool:
    """True unless config explicitly restores the historical OpenRouter fallthrough."""
    try:
        from hermes_cli.config import load_config

        sec = (load_config() or {}).get("security") or {}
        wallet = sec.get("billing_wallet") if isinstance(sec, dict) else {}
        if not isinstance(wallet, dict) or "bind_company_keys" not in wallet:
            return True
        return bool(wallet.get("bind_company_keys"))
    except Exception:
        return True


def company_openrouter_wallet_eligible(
    *, requested: str, bind_enabled: Optional[bool] = None,
) -> bool:
    """Whether the company OpenRouter key may attach to this request."""
    if bind_enabled is None:
        bind_enabled = billing_wallet_bind_enabled()
    if not bind_enabled:
        return True
    return (requested or "").strip().lower() in _COMPANY_OPENROUTER_REQUESTS


def allow_aggregator_auto_switch(
    *, model_name: str, current_provider: str, target_provider: str,
    bind_enabled: Optional[bool] = None,
) -> bool:
    """False: do not hop the session onto a metered aggregator from another vendor.

    Having the aggregator's key is not consent — that is the remaining hole after #506.
    Explicit selection (``/model openrouter``, ``openrouter/…``, ``openrouter:…``) still hops.
    """
    if bind_enabled is None:
        bind_enabled = billing_wallet_bind_enabled()
    if not bind_enabled:
        return True
    target = (target_provider or "").strip().lower()
    if target not in METERED_AGGREGATORS:
        return True
    current = (current_provider or "").strip().lower()
    if current in {"", "auto"} or current == target:
        return True
    name = (model_name or "").strip().lower()
    if not name:
        return False
    if name == target or name.startswith(f"{target}/") or name.startswith(f"{target}:"):
        return True
    return False


def aggregator_api_key_candidates(
    *, requested: str, explicit_api_key: Optional[str], company_keys: Iterable[Optional[str]],
    bind_enabled: Optional[bool] = None,
) -> list[str]:
    """Keys allowed for an OpenRouter destination. Company keys only when wallet-eligible."""
    explicit = str(explicit_api_key or "").strip()
    company = [str(k).strip() for k in company_keys if str(k or "").strip()]
    if company_openrouter_wallet_eligible(requested=requested, bind_enabled=bind_enabled):
        return [explicit, *company] if explicit else list(company)
    # Reverse: the requestor pays. Company wallet stays closed.
    return [explicit] if explicit else []


def target_is_official_host(target_url: str, official_hosts: Iterable[str]) -> bool:
    """True when ``target_url`` is empty (vendor default) or matches an official host.

    Uses hostname matching, not substring search, so ``api.tavily.com.evil`` does not pass.
    """
    url = (target_url or "").strip()
    if not url:
        return True
    from utils import base_url_host_matches

    return any(base_url_host_matches(url, host) for host in official_hosts if host)


def company_secret_for_official_host(
    *, company_secret: str, target_url: str, official_hosts: Iterable[str],
    explicit_secret: str = "", destination: str = "", bind_enabled: Optional[bool] = None,
) -> str:
    """Return the key allowed for ``target_url``.

    Official / default host: explicit key, else company key.
    Redirected host: explicit (requestor-pays) only. Company key is withheld.
    """
    explicit = str(explicit_secret or "").strip()
    company = str(company_secret or "").strip()
    if bind_enabled is None:
        bind_enabled = billing_wallet_bind_enabled()
    if not bind_enabled or target_is_official_host(target_url, official_hosts):
        return explicit or company
    dest = destination or (target_url or "")
    if explicit:
        record_billing_hijack(
            reason="redirected-host-requestor-pays", requested=dest,
            destination=target_url, requestor_paid=True,
        )
        return explicit
    if company:
        record_billing_hijack(
            reason="redirected-host-blocked", requested=dest,
            destination=target_url, requestor_paid=False,
        )
    return ""


def bound_vendor_secret(
    *, vendor: str, company_secret: str, target_url: str, explicit_secret: str = "",
    bind_enabled: Optional[bool] = None,
) -> str:
    """``company_secret_for_official_host`` keyed by ``METERED_TOOL_HOSTS[vendor]``."""
    hosts = METERED_TOOL_HOSTS.get((vendor or "").strip().lower())
    if not hosts:
        return str(explicit_secret or company_secret or "").strip()
    return company_secret_for_official_host(
        company_secret=company_secret, target_url=target_url, official_hosts=hosts,
        explicit_secret=explicit_secret, destination=vendor, bind_enabled=bind_enabled,
    )


def record_billing_hijack(
    *, reason: str, requested: str, destination: str, requestor_paid: bool,
) -> None:
    """Log a hijack attempt (no secrets). Best-effort JSONL under the profile logs dir."""
    logger.warning(
        "billing-hijack %s requested=%s destination=%s requestor_paid=%s",
        reason, requested, destination, requestor_paid,
    )
    rec = {
        "ts": time.time(),
        "reason": reason,
        "requested": requested,
        "destination": destination,
        "requestor_paid": requestor_paid,
    }
    try:
        from hermes_constants import get_hermes_home

        path = Path(get_hermes_home()) / "logs" / "billing-hijack.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    except Exception:
        logger.debug("billing-hijack audit write failed", exc_info=True)

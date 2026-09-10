"""Company-wallet binding against metered-aggregator billing hijacks.

A hijack reroutes inference onto OpenRouter (or another metered aggregator) so the *operator's*
key pays (#97487, the $100 Astra incident, and the last-rung OpenRouter fallthrough). Reverse:

* company aggregator keys attach only when the operator selected that aggregator (or auto /
  custom / local, where OpenRouter is the product default);
* a requestor-supplied key still attaches — they pay for the route they injected;
* otherwise fail closed (no empty-key OpenRouter call that silently bills).

``security.billing_wallet.bind_company_keys`` (default True) is the kill switch for the
historical last-rung fallthrough. No ``HERMES_*`` env var — this is behavioral config.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# Aggregators whose auto-detect hop bills a third party. Nous stays off this list: it is the
# product home, and static detection already refuses auto-switch TO aggregators.
METERED_AGGREGATORS = frozenset({"openrouter", "ai-gateway", "kilocode"})

# Last-rung OpenRouter may spend the company OPENROUTER_API_KEY only for these requested ids.
# A named vendor (deepseek, anthropic, nous, openai-codex, …) that falls through is a hijack.
_COMPANY_OPENROUTER_REQUESTS = frozenset({"", "auto", "openrouter", "custom", "local"})


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

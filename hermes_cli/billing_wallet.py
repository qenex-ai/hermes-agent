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
    "anthropic": ("api.anthropic.com",),
    "browserbase": ("api.browserbase.com",),
    "browser-use": ("api.browser-use.com",),
    "exa": ("api.exa.ai",),
    "parallel": ("api.parallel.ai",),
    "keenable": ("api.keenable.ai",),
    "brave": ("api.search.brave.com",),
    "fal": ("fal.ai", "queue.fal.run", "fal.run"),
    "krea": ("api.krea.ai",),
    "minimax": ("api.minimax.io", "api.minimaxi.com"),
    "mistral": ("api.mistral.ai",),
}

# Paid backends that must not be auto-selected just because the company key exists.
# Explicit ``hermes tools`` / config.yaml selection still spends the company wallet.
# Self-hosted (searxng, FIRECRAWL_API_URL, local browser, ddgs) stay off this list.
METERED_AUTOSELECT: frozenset[str] = frozenset({
    "tavily", "perplexity", "exa", "parallel", "keenable", "brave-free", "brave",
    "xai", "firecrawl", "openrouter", "ai-gateway", "kilocode",
    "fal", "krea", "openai", "deepinfra", "together", "replicate",
    "browser-use", "browserbase", "browser_use", "elevenlabs", "groq",
})

# Child-process env: unofficial ``*_BASE_URL`` must not inherit company keys.
# (key env vars, base-url env vars, vendor id in METERED_TOOL_HOSTS)
_CHILD_ENV_BINDINGS: tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...] = (
    (("OPENROUTER_API_KEY",), ("OPENROUTER_API_BASE", "OPENROUTER_BASE_URL"), "openrouter"),
    (("OPENAI_API_KEY",), ("OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENAI_REALTIME_URL", "STT_OPENAI_BASE_URL"), "openai"),
    (("ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN"), ("ANTHROPIC_BASE_URL",), "anthropic"),
    (
        ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY"),
        ("GEMINI_API_BASE", "GEMINI_BASE_URL", "GOOGLE_GEMINI_BASE_URL", "GOOGLE_API_BASE", "API_BASE"),
        "gemini",
    ),
    (("FIRECRAWL_API_KEY",), ("FIRECRAWL_API_URL",), "firecrawl"),
    (("TAVILY_API_KEY",), ("TAVILY_BASE_URL",), "tavily"),
    (("EXA_API_KEY",), ("EXA_API_URL", "EXA_BASE_URL"), "exa"),
    (("PARALLEL_API_KEY",), ("PARALLEL_API_URL", "PARALLEL_BASE_URL"), "parallel"),
    (("PERPLEXITY_API_KEY",), ("PERPLEXITY_API_URL", "PERPLEXITY_BASE_URL"), "perplexity"),
    (("KEENABLE_API_KEY",), ("KEENABLE_API_URL", "KEENABLE_BASE_URL"), "keenable"),
    (("BRAVE_SEARCH_API_KEY",), ("BRAVE_SEARCH_API_URL", "BRAVE_API_URL"), "brave"),
    (("ELEVENLABS_API_KEY",), ("ELEVENLABS_API_URL", "ELEVENLABS_BASE_URL"), "elevenlabs"),
    (("GROQ_API_KEY",), ("GROQ_API_BASE", "GROQ_BASE_URL"), "groq"),
    (("XAI_API_KEY",), ("XAI_API_BASE", "XAI_BASE_URL"), "xai"),
    (("BROWSERBASE_API_KEY",), ("BROWSERBASE_API_URL", "BROWSERBASE_BASE_URL"), "browserbase"),
    (("BROWSER_USE_API_KEY",), ("BROWSER_USE_API_URL", "BROWSER_USE_BASE_URL"), "browser-use"),
    (("FAL_KEY",), ("FAL_KEY_BASE_URL", "FAL_BASE_URL"), "fal"),
    (("KREA_API_KEY",), ("KREA_API_URL", "KREA_BASE_URL"), "krea"),
    (("MISTRAL_API_KEY",), ("MISTRAL_API_BASE", "MISTRAL_BASE_URL"), "mistral"),
    (("MINIMAX_API_KEY", "MINIMAX_CN_API_KEY"), ("MINIMAX_BASE_URL", "MINIMAX_API_HOST"), "minimax"),
)


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


def allow_metered_autoselect(
    backend: str, *, bind_enabled: Optional[bool] = None,
) -> bool:
    """False: do not pick this paid backend just because its company key is in the env.

    Having ``EXA_API_KEY`` / ``FAL_KEY`` / ``BROWSER_USE_API_KEY`` is not consent to
    spend it on a never-configured session. Explicit ``web.backend`` /
    ``image_gen.provider`` / ``browser.cloud_provider`` still wins at the call site.
    """
    if bind_enabled is None:
        bind_enabled = billing_wallet_bind_enabled()
    if not bind_enabled:
        return True
    return (backend or "").strip().lower() not in METERED_AUTOSELECT


def bind_child_env(
    env: Mapping[str, str], *, bind_enabled: Optional[bool] = None,
) -> dict[str, str]:
    """Strip company vendor keys from a child env when a matching base URL is unofficial.

    Fail closed: process env cannot distinguish requestor vs company keys, so unofficial
    hosts lose every listed key. Official / empty base URLs are unchanged.
    """
    out = dict(env)
    if bind_enabled is None:
        bind_enabled = billing_wallet_bind_enabled()
    if not bind_enabled:
        return out
    stripped: list[str] = []
    unofficial: list[str] = []
    for key_vars, url_vars, vendor in _CHILD_ENV_BINDINGS:
        hosts = METERED_TOOL_HOSTS.get(vendor)
        if not hosts:
            continue
        urls = [str(out.get(name) or "").strip() for name in url_vars]
        urls = [u for u in urls if u]
        if not urls:
            continue
        bad = [u for u in urls if not target_is_official_host(u, hosts)]
        if not bad:
            continue
        unofficial.extend(bad)
        for name in key_vars:
            if out.pop(name, None) is not None:
                stripped.append(name)
    if stripped:
        record_billing_hijack(
            reason="child-env-redirected-host-blocked",
            requested=",".join(stripped),
            destination=";".join(unofficial[:4]),
            requestor_paid=False,
        )
    return out


def web_company_secret(
    *, backend: str, company_secret: str, target_url: str = "",
    bind_enabled: Optional[bool] = None,
) -> str:
    """Company key for a metered web backend only when the operator selected it.

    Unused ``EXA_API_KEY`` / ``TAVILY_API_KEY`` sitting in ``.env`` must not attach
    just because a keyless walk landed on that vendor. Self-hosted Firecrawl
    (``FIRECRAWL_API_URL`` set) counts as an operator pick of infrastructure.
    """
    backend_l = (backend or "").strip().lower()
    vendor = "brave" if backend_l == "brave-free" else backend_l
    selected = False
    try:
        from plugins.web.keyless_mcp import _web_config_selects

        selected = bool(_web_config_selects(backend_l) or _web_config_selects(vendor))
    except Exception:
        selected = False
    if (target_url or "").strip() and backend_l == "firecrawl":
        selected = True
    secret = company_secret
    if not selected and not allow_metered_autoselect(backend_l, bind_enabled=bind_enabled):
        secret = ""
    return bound_vendor_secret(
        vendor=vendor, company_secret=secret, target_url=target_url, bind_enabled=bind_enabled,
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

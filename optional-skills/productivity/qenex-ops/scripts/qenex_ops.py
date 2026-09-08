#!/usr/bin/env python3
"""QENEX LTD Lab ops loop — classify inbound, draft replies, never send or spend.

This is a cron ``no_agent`` script: zero LLM tokens per tick. It does not make the
company legally autonomous, maximize profit, or eliminate hosting/compute cost.
It runs the only honest zero-token loop: Lab-license funnel, human gates for
money/legal, Pulse stays archived.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

JOB_NAME = "qenex-ops-tick"
STATE_DIRNAME = "qenex-ops"
SCRIPT_NAME = "qenex_ops.py"
SKILL_NAME = "qenex-ops"
CONTACT_EMAIL = "ceo@qenex.ai"
LAB_URL = "https://lab.qenex.ai"
VERIFIER_URL = "https://github.com/qenex-ai/qenex-verifier"
ALLOWED_PRODUCT = "lab"

# Hard invariants. Config cannot flip these on — a "zero-cost autonomous CEO"
# that wires money or outbound mail is the failure mode this loop exists to block.
AUTO_SEND = False
SPEND_ALLOWED = False

_LAB_KEYWORDS = (
    "qenex lab",
    "lab.qenex.ai",
    "quantum chemistry",
    "hartree-fock",
    "ccsd",
    "dft",
    "provenance",
    ".qlang",
    "ukamf",
    "chemrxiv",
    "computational chemistry",
    "materials group",
    "chemistry group",
    "academic license",
    "license quote",
    "license pricing",
    "trial access",
    "sovereign",
    "air-gapped",
)
_VERIFIER_KEYWORDS = (
    "qenex-verifier",
    "zenodo",
    "10.5281/zenodo.20083483",
    "bit-for-bit",
    "reproduce the tables",
    "atoms.json",
)
_PULSE_KEYWORDS = (
    "qenex pulse",
    "pulse.qenex.ai",
    "third-party-risk",
    "third party risk",
    "third-party risk",
)
_HUMAN_GATE_KEYWORDS = (
    "companies house",
    "confirmation statement",
    "vat",
    "hmrc",
    "patent",
    "gb2613981",
    "wire transfer",
    "bank details",
    "swift",
    "iban",
    "sign the contract",
    "nda",
    "pay this invoice",
    "tax return",
    "director duties",
)
_SPEND_KEYWORDS = (
    "buy ads",
    "run ads",
    "google ads",
    "paid campaign",
    "hire a",
    "purchase gpu",
    "rent gpu",
    "subscribe to openai",
    "upgrade the model",
    "pay for compute",
    "spin up a cluster",
    "order a vps",
)
_REVENUE_KEYWORDS = (
    "buy a license",
    "purchase a license",
    "want a license",
    "licence quote",
    "licensing",
    "procurement",
    "po for lab",
    "purchase order for lab",
)

# Higher rank = process first. spend_refuse is checked before revenue so a
# "buy ads to sell licenses" note cannot be filed as a Lab lead.
_KIND_RANK = {
    "spend_refuse": 1000,
    "human_gate": 900,
    "lab_license": 100,
    "verifier_signal": 80,
    "pulse_archive": 40,
    "noise": 0,
}


@dataclass(frozen=True)
class Classification:
    kind: str
    rank: int
    matched: tuple[str, ...]
    send: bool = False
    spend: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["matched"] = list(self.matched)
        data["send"] = False
        data["spend"] = False
        return data


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_home(explicit: Optional[Path] = None) -> Path:
    if explicit is not None:
        return Path(explicit)
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except Exception as exc:
        raise SystemExit(f"HERMES_HOME is not set ({exc})") from exc


def state_dir(home: Path) -> Path:
    return home / STATE_DIRNAME


def _haystack(item: dict[str, Any]) -> str:
    parts = [
        str(item.get("from") or ""),
        str(item.get("subject") or ""),
        str(item.get("body") or ""),
        str(item.get("source") or ""),
        str(item.get("url") or ""),
    ]
    return " ".join(parts).lower()


def _matches(text: str, keywords: Iterable[str]) -> tuple[str, ...]:
    return tuple(k for k in keywords if k in text)


def classify(item: dict[str, Any]) -> Classification:
    """Map an inbound item to one kind. Send and spend are always false."""
    text = _haystack(item)
    spend_hits = _matches(text, _SPEND_KEYWORDS)
    if spend_hits:
        return Classification("spend_refuse", _KIND_RANK["spend_refuse"], spend_hits)
    revenue_hits = _matches(text, _REVENUE_KEYWORDS)
    lab_hits = _matches(text, _LAB_KEYWORDS)
    if revenue_hits or lab_hits:
        return Classification(
            "lab_license",
            _KIND_RANK["lab_license"],
            revenue_hits + lab_hits,
        )
    gate_hits = _matches(text, _HUMAN_GATE_KEYWORDS)
    if gate_hits:
        return Classification("human_gate", _KIND_RANK["human_gate"], gate_hits)
    verifier_hits = _matches(text, _VERIFIER_KEYWORDS)
    if verifier_hits:
        return Classification("verifier_signal", _KIND_RANK["verifier_signal"], verifier_hits)
    pulse_hits = _matches(text, _PULSE_KEYWORDS)
    if pulse_hits:
        return Classification("pulse_archive", _KIND_RANK["pulse_archive"], pulse_hits)
    return Classification("noise", _KIND_RANK["noise"], ())


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ledger_path(home: Path) -> Path:
    return state_dir(home) / "ledger.json"


def default_ledger() -> dict[str, Any]:
    return {
        "product": ALLOWED_PRODUCT,
        "auto_send": AUTO_SEND,
        "spend_allowed": SPEND_ALLOWED,
        "contact_email": CONTACT_EMAIL,
        "lab_url": LAB_URL,
        "verifier_url": VERIFIER_URL,
        "created_at": _now_iso(),
    }


def load_ledger(home: Path) -> dict[str, Any]:
    data = _load_json(_ledger_path(home), default_ledger())
    # Invariants win over any file the user edits.
    data["auto_send"] = AUTO_SEND
    data["spend_allowed"] = SPEND_ALLOWED
    data["product"] = ALLOWED_PRODUCT
    return data


def _ensure_dirs(home: Path) -> dict[str, Path]:
    root = state_dir(home)
    paths = {
        "root": root,
        "inbox": root / "inbox",
        "drafts": root / "drafts",
        "approvals": root / "approvals",
        "refused": root / "refused",
        "processed": root / "processed",
        "noise": root / "noise",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def _skill_root() -> Path:
    here = Path(__file__).resolve().parent
    if (here.parent / "SKILL.md").is_file():
        return here.parent
    env_home = os.environ.get("HERMES_HOME")
    if env_home:
        installed = Path(env_home) / "skills" / SKILL_NAME
        if (installed / "SKILL.md").is_file():
            return installed
    return here.parent


def _install_skill(home: Path) -> Path:
    dest = home / "skills" / SKILL_NAME
    src = _skill_root()
    dest.mkdir(parents=True, exist_ok=True)
    for rel in (
        "SKILL.md",
        "scripts/qenex_ops.py",
        "references/human-gates.md",
        "templates/inbox-item.json",
    ):
        src_file = src / rel
        if not src_file.is_file():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, target)
    return dest


def _install_cron_script(home: Path) -> Path:
    dest = home / "scripts" / SCRIPT_NAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).resolve(), dest)
    return dest


def _create_cron_job(schedule: str) -> dict[str, Any]:
    from cron.jobs import create_job, list_jobs

    for job in list_jobs(include_disabled=True):
        if job.get("name") == JOB_NAME:
            return {"created": False, "id": job.get("id"), "name": JOB_NAME}
    job = create_job(
        prompt=None,
        schedule=schedule,
        name=JOB_NAME,
        script=SCRIPT_NAME,
        no_agent=True,
        deliver="local",
    )
    return {"created": True, "id": job["id"], "name": job["name"], "no_agent": True}


def setup(
    *,
    home: Optional[Path] = None,
    schedule: str = "every 30m",
    create_cron: bool = True,
) -> dict[str, Any]:
    home = resolve_home(home)
    paths = _ensure_dirs(home)
    ledger = default_ledger()
    _write_json(_ledger_path(home), ledger)
    skill_dest = _install_skill(home)
    script_dest = _install_cron_script(home)
    cron_info: dict[str, Any] = {"created": False, "skipped": True}
    if create_cron:
        cron_info = _create_cron_job(schedule)
    receipt = {
        "ok": True,
        "home": str(home),
        "state": str(paths["root"]),
        "skill": str(skill_dest),
        "script": str(script_dest),
        "cron": cron_info,
        "invariants": {
            "auto_send": AUTO_SEND,
            "spend_allowed": SPEND_ALLOWED,
            "product": ALLOWED_PRODUCT,
            "no_agent": True,
        },
        "honest_limits": [
            "UK director duties, filings, and contracts stay human.",
            "No outbound mail or payment is sent.",
            "LLM cost is zero on the tick; hosting and Lab compute are not free.",
        ],
    }
    _write_json(paths["root"] / "setup-receipt.json", receipt)
    return receipt


def enqueue(
    *,
    home: Optional[Path] = None,
    sender: str,
    subject: str,
    body: str,
    source: str = "manual",
    item_id: Optional[str] = None,
    url: str = "",
) -> Path:
    home = resolve_home(home)
    paths = _ensure_dirs(home)
    item_id = item_id or f"item-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"
    dest = paths["inbox"] / f"{item_id}.json"
    _write_json(
        dest,
        {
            "id": item_id,
            "from": sender,
            "subject": subject,
            "body": body,
            "source": source,
            "url": url,
            "received_at": _now_iso(),
        },
    )
    return dest


def _draft_body(item: dict[str, Any], kind: str) -> str:
    sender = item.get("from") or "there"
    if kind == "lab_license":
        return (
            f"Hello {sender},\n\n"
            "Thanks for reaching QENEX LTD about QENEX Lab. The Lab is the only "
            f"product we sell: sovereign quantum chemistry with cryptographic provenance "
            f"({LAB_URL}). The Apache-2.0 verifier subset is at {VERIFIER_URL} so you "
            "can reproduce published numeric claims on your own machine before a license "
            "conversation.\n\n"
            "This message is a draft. A human director will send it and agree any "
            f"price. Contact: {CONTACT_EMAIL}.\n"
        )
    if kind == "verifier_signal":
        return (
            f"Hello {sender},\n\n"
            "If you reproduced the verifier tables, you already have the public proof "
            f"surface. Licensed Lab access (full methods, air-gapped deploy) is a "
            f"separate conversation with a human at {CONTACT_EMAIL}. Draft only — not sent.\n"
        )
    if kind == "pulse_archive":
        return (
            f"Hello {sender},\n\n"
            "QENEX Pulse is archived and is not sold. QENEX LTD is focused on QENEX Lab "
            f"({LAB_URL}). Existing Pulse users can reach {CONTACT_EMAIL} for migration "
            "support. Draft only — not sent.\n"
        )
    if kind == "human_gate":
        return (
            "Held for a human director. Money, filings, patents, and contracts are "
            "not agent-actionable. No draft will be sent and no payment will be made.\n"
        )
    return ""


def _bucket_for(kind: str, paths: dict[str, Path]) -> Path:
    return {
        "lab_license": paths["drafts"],
        "verifier_signal": paths["drafts"],
        "pulse_archive": paths["drafts"],
        "human_gate": paths["approvals"],
        "spend_refuse": paths["refused"],
        "noise": paths["noise"],
    }[kind]


def tick(*, home: Optional[Path] = None) -> dict[str, Any]:
    home = resolve_home(home)
    paths = _ensure_dirs(home)
    ledger = load_ledger(home)
    _write_json(_ledger_path(home), ledger)
    assert ledger["auto_send"] is False
    assert ledger["spend_allowed"] is False
    seen_path = state_dir(home) / "seen.json"
    seen = set(_load_json(seen_path, []))
    results: list[dict[str, Any]] = []
    inbox_files = sorted(paths["inbox"].glob("*.json"))
    for path in inbox_files:
        item = _load_json(path, {})
        item_id = str(item.get("id") or path.stem)
        if item_id in seen:
            path.replace(paths["processed"] / path.name)
            continue
        classification = classify(item)
        record = {
            "id": item_id,
            "kind": classification.kind,
            "rank": classification.rank,
            "matched": list(classification.matched),
            "send": False,
            "spend": False,
            "from": item.get("from"),
            "subject": item.get("subject"),
            "source": item.get("source"),
            "processed_at": _now_iso(),
        }
        if classification.kind == "spend_refuse":
            record["reason"] = "Refused: this loop never spends money."
        body = _draft_body(item, classification.kind)
        if body:
            record["draft"] = body
            record["send"] = False
        dest = _bucket_for(classification.kind, paths) / f"{item_id}.json"
        _write_json(dest, {**item, "classification": classification.to_dict(), "ops": record})
        path.replace(paths["processed"] / path.name)
        seen.add(item_id)
        results.append(record)
    _write_json(seen_path, sorted(seen))
    actionable = [r for r in results if r["kind"] != "noise"]
    summary = {
        "ok": True,
        "ticks": _now_iso(),
        "scanned": len(inbox_files),
        "actionable": len(actionable),
        "auto_send": False,
        "spend_allowed": False,
        "product": ALLOWED_PRODUCT,
        "items": sorted(actionable, key=lambda r: r["rank"], reverse=True),
    }
    _write_json(state_dir(home) / "last-tick.json", summary)
    return summary


def status(*, home: Optional[Path] = None) -> dict[str, Any]:
    home = resolve_home(home)
    paths = _ensure_dirs(home)
    ledger = load_ledger(home)
    counts = {name: len(list(path.glob("*.json"))) for name, path in paths.items() if path != paths["root"]}
    return {
        "home": str(home),
        "ledger": ledger,
        "queues": counts,
        "last_tick": _load_json(state_dir(home) / "last-tick.json", None),
    }


def _print_json(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="QENEX LTD Lab ops: classify, draft, never send or spend.",
    )
    parser.add_argument(
        "--home",
        default=None,
        help="Hermes home (default: HERMES_HOME / get_hermes_home())",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    setup_p = sub.add_parser("setup", aliases=["init"], help="Install state, skill, zero-token cron tick")
    setup_p.add_argument("--schedule", default="every 30m")
    setup_p.add_argument("--no-cron", action="store_true", help="Skip creating the cron job")

    sub.add_parser("tick", help="Process the inbox (cron entrypoint; silent if empty)")
    sub.add_parser("status", aliases=["st"], help="Show queue counts")

    enq = sub.add_parser("enqueue", aliases=["add"], help="Drop an inbox JSON item")
    enq.add_argument("--from", dest="sender", required=True)
    enq.add_argument("--subject", required=True)
    enq.add_argument("--body", required=True)
    enq.add_argument("--source", default="manual")
    enq.add_argument("--id", dest="item_id", default=None)
    enq.add_argument("--url", default="")

    args = parser.parse_args(argv)
    home = Path(args.home) if args.home else None

    def _cmd_setup() -> dict[str, Any]:
        return setup(home=home, schedule=args.schedule, create_cron=not args.no_cron)

    def _cmd_tick() -> dict[str, Any]:
        summary = tick(home=home)
        return summary if summary["actionable"] else {}

    def _cmd_status() -> dict[str, Any]:
        return status(home=home)

    def _cmd_enqueue() -> dict[str, Any]:
        path = enqueue(
            home=home,
            sender=args.sender,
            subject=args.subject,
            body=args.body,
            source=args.source,
            item_id=args.item_id,
            url=args.url,
        )
        return {"ok": True, "path": str(path)}

    handlers = {
        "setup": _cmd_setup,
        "init": _cmd_setup,
        "tick": _cmd_tick,
        "status": _cmd_status,
        "st": _cmd_status,
        "enqueue": _cmd_enqueue,
        "add": _cmd_enqueue,
    }
    payload = handlers[args.command]()
    if payload:
        _print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

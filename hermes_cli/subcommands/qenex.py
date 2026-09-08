"""``hermes qenex`` — QENEX LTD Lab ops loop (zero-token tick).

Installs state, copies the cron script into ``$HERMES_HOME/scripts/``, and
creates a ``no_agent`` job. Does not send mail, spend money, or replace a
UK director. The builtin cron ticker only runs inside the gateway.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Optional

_REPO_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "optional-skills"
    / "productivity"
    / "qenex-ops"
    / "scripts"
    / "qenex_ops.py"
)


def _load_ops():
    from hermes_constants import get_hermes_home

    candidates = (_REPO_SCRIPT, Path(get_hermes_home()) / "scripts" / "qenex_ops.py")
    script = next((p for p in candidates if p.is_file()), None)
    if script is None:
        raise SystemExit(
            "qenex-ops script not found. Run from a checkout that includes "
            "optional-skills/productivity/qenex-ops, or copy qenex_ops.py into "
            "$HERMES_HOME/scripts/."
        )
    spec = importlib.util.spec_from_file_location("qenex_ops_cli", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _print_json(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def cmd_qenex(args: argparse.Namespace) -> int:
    """Dispatch ``hermes qenex <setup|tick|status|enqueue>``."""
    command = getattr(args, "qenex_command", None)
    if not command:
        print(
            "usage: hermes qenex <setup|tick|status|enqueue>\n"
            "\n"
            "Zero-token Lab ops loop. Does not send, spend, or file Companies House.\n"
            "  setup / init     Install state + no_agent cron tick\n"
            "  tick             Process inbox + mailbox/*.eml (silent if empty)\n"
            "  status / st      Queue counts\n"
            "  enqueue / add    Drop one inbox item\n"
            "\n"
            "Jobs fire only while the gateway cron ticker is running:\n"
            "  hermes gateway install",
            file=sys.stderr,
        )
        return 1

    ops = _load_ops()
    home: Optional[Path] = Path(args.home) if getattr(args, "home", None) else None

    def _setup() -> dict[str, Any]:
        return ops.setup(
            home=home,
            schedule=getattr(args, "schedule", "every 30m"),
            create_cron=not getattr(args, "no_cron", False),
        )

    def _tick() -> dict[str, Any]:
        summary = ops.tick(home=home)
        return summary if summary.get("actionable") else {}

    def _status() -> dict[str, Any]:
        return ops.status(home=home)

    def _enqueue() -> dict[str, Any]:
        path = ops.enqueue(
            home=home,
            sender=args.sender,
            subject=args.subject,
            body=args.body,
            source=getattr(args, "source", "manual"),
            item_id=getattr(args, "item_id", None),
            url=getattr(args, "url", "") or "",
        )
        return {"ok": True, "path": str(path)}

    handlers = {
        "setup": _setup,
        "init": _setup,
        "tick": _tick,
        "status": _status,
        "st": _status,
        "enqueue": _enqueue,
        "add": _enqueue,
    }
    payload = handlers[command]()
    if payload:
        _print_json(payload)
    if command in {"setup", "init"} and payload and payload.get("gateway", {}).get("running") is False:
        print(
            "Gateway is not running — the no_agent tick will not fire until "
            "`hermes gateway install` (or `sudo hermes gateway install --system`).",
            file=sys.stderr,
        )
    return 0


def build_qenex_parser(subparsers) -> None:
    """Attach the ``qenex`` subcommand to ``subparsers``."""
    parser = subparsers.add_parser(
        "qenex",
        help="QENEX LTD Lab ops: classify, draft, never send or spend",
        description="Install and run the zero-token QENEX Lab ops loop. "
        "Not a fully autonomous company: no send, no spend, no filings. "
        "Cron ticks only fire while the Hermes gateway is running.",
    )
    parser.add_argument(
        "--home",
        default=None,
        help="Hermes home (default: HERMES_HOME / get_hermes_home())",
    )
    sub = parser.add_subparsers(dest="qenex_command")

    setup_p = sub.add_parser("setup", aliases=["init"], help="Install state and no_agent cron tick")
    setup_p.add_argument("--schedule", default="every 30m")
    setup_p.add_argument("--no-cron", action="store_true", help="Skip creating the cron job")

    sub.add_parser("tick", help="Process inbox and mailbox/*.eml")
    sub.add_parser("status", aliases=["st"], help="Show queue counts")

    enq = sub.add_parser("enqueue", aliases=["add"], help="Drop an inbox JSON item")
    enq.add_argument("--from", dest="sender", required=True)
    enq.add_argument("--subject", required=True)
    enq.add_argument("--body", required=True)
    enq.add_argument("--source", default="manual")
    enq.add_argument("--id", dest="item_id", default=None)
    enq.add_argument("--url", default="")

    parser.set_defaults(func=cmd_qenex)

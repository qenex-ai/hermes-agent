"""Build a Cursor SDK request payload and shell to the TypeScript runner.

SDK calls live in ``scripts/cursor-sdk`` (there is no first-party Python SDK).
This module is the DI-testable Python seam: payload construction, runtime
selection, and subprocess exit-code plumbing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from hermes_constants import display_hermes_home, get_hermes_home

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "scripts" / "cursor-sdk"
CLI_ENTRY = PACKAGE_DIR / "src" / "cli.ts"
DEFAULT_MODEL = "composer-2"
CLOUD_AGENT_PREFIX = "bc-"

_EXIT_OK = 0
_EXIT_STARTUP = 1


class CursorSdkError(ValueError):
    """User-facing configuration / routing error (maps to exit 1)."""


def _config_section() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        cfg = load_config() or {}
        section = cfg.get("cursor_sdk")
        return dict(section) if isinstance(section, dict) else {}
    except Exception:
        return {}


def resolve_api_key(explicit: str | None) -> str:
    """Always pass apiKey explicitly to the SDK — never rely on implicit env lookup there."""
    key = (explicit or os.environ.get("CURSOR_API_KEY") or "").strip()
    if not key:
        raise CursorSdkError(
            "Missing CURSOR_API_KEY. Mint a user or service-account key at "
            "https://cursor.com/dashboard/cloud-agents and store it in "
            f"{display_hermes_home()}/.env (secrets only)."
        )
    return key


def resolve_runtime(args: Any) -> str:
    local = bool(getattr(args, "local", False))
    cloud = bool(getattr(args, "cloud", False))
    if local and cloud:
        raise CursorSdkError("Pass exactly one of --local or --cloud, not both.")
    if not local and not cloud:
        raise CursorSdkError(
            "Runtime must be explicit: pass --local (cwd) or --cloud (repo URL). "
            "Omitting both silently defaults the SDK to local — that is a trap."
        )
    return "local" if local else "cloud"


def _load_mcp(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    raw = Path(path).expanduser().read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise CursorSdkError("--mcp-json must be a JSON object of {name: serverConfig}")
    return data


def build_request(args: Any, *, cwd: str | None = None) -> dict[str, Any]:
    """Pure mapping from argparse namespace → SdkRequest JSON."""
    action = getattr(args, "cursor_sdk_command", None)
    if action in ("ls",):
        action = "list"
    if action not in {"prompt", "send", "resume", "get", "get-run", "list"}:
        raise CursorSdkError(
            "usage: hermes cursor-sdk <prompt|send|resume|get|get-run|list> …"
        )

    runtime = resolve_runtime(args)
    cfg = _config_section()
    local_cfg = cfg.get("local") if isinstance(cfg.get("local"), dict) else {}
    cloud_cfg = cfg.get("cloud") if isinstance(cfg.get("cloud"), dict) else {}

    prompt_bits = list(getattr(args, "prompt", None) or [])
    prompt = " ".join(str(p) for p in prompt_bits).strip()
    if action == "resume":
        agent_id = getattr(args, "agent_id", None)
        if not agent_id:
            raise CursorSdkError("resume requires an agent ID")
        if not prompt:
            raise CursorSdkError("resume requires a prompt")
    else:
        agent_id = getattr(args, "agent_id", None)

    run_id = getattr(args, "run_id", None)
    if action == "get-run":
        if not run_id:
            raise CursorSdkError("get-run requires a run ID")
        if str(run_id).startswith(CLOUD_AGENT_PREFIX):
            raise CursorSdkError(
                f"{run_id} is a cloud agent ID (bc- prefix), not a run ID. "
                "Use `hermes cursor-sdk get <agentId>` or pass the run UUID."
            )

    if action in {"prompt", "send"} and not prompt:
        raise CursorSdkError(f"{action} requires a prompt")

    follow_ups = [str(f).strip() for f in (getattr(args, "follow_up", None) or []) if str(f).strip()]
    if follow_ups and action != "send":
        raise CursorSdkError("--follow-up is only valid on `send` (durable create+send)")

    setting_sources = getattr(args, "setting_sources", None)
    if setting_sources is None:
        setting_sources = local_cfg.get("setting_sources", [])
    if isinstance(setting_sources, str):
        setting_sources = [s.strip() for s in setting_sources.split(",") if s.strip()]
    if setting_sources is None:
        setting_sources = []

    cwd_path = getattr(args, "cwd", None) or cwd or os.getcwd()
    repo = getattr(args, "repo", None) or cloud_cfg.get("repo")
    starting_ref = getattr(args, "ref", None) or cloud_cfg.get("starting_ref") or "main"
    repos = [{"url": repo, "startingRef": starting_ref}] if repo else []

    skip_reviewer = getattr(args, "skip_reviewer_request", None)
    if skip_reviewer is None:
        skip_reviewer = cloud_cfg.get("skip_reviewer_request", True)

    auto_pr = bool(getattr(args, "auto_create_pr", False) or cloud_cfg.get("auto_create_pr", False))
    model = (getattr(args, "model", None) or cfg.get("model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL

    request: dict[str, Any] = {
        "pattern": action,
        "apiKey": resolve_api_key(getattr(args, "api_key", None)),
        "model": model,
        "runtime": runtime,
        "cwd": str(cwd_path),
        "repos": repos,
        "skipReviewerRequest": bool(skip_reviewer),
        "autoCreatePR": auto_pr,
        "settingSources": list(setting_sources),
        "stream": not bool(getattr(args, "no_stream", False)),
        "cancelAfterMs": getattr(args, "cancel_after_ms", None),
    }
    if prompt:
        request["prompt"] = prompt
    if follow_ups:
        request["followUps"] = follow_ups
    if agent_id:
        request["agentId"] = agent_id
    if run_id:
        request["runId"] = run_id
    mcp = _load_mcp(getattr(args, "mcp_json", None))
    if mcp:
        request["mcpServers"] = mcp
    return request


def find_node() -> str:
    node = shutil.which("node")
    if not node:
        raise CursorSdkError(
            "Node.js >= 22.13 is required for @cursor/sdk. Install Node and retry."
        )
    return node


def ensure_package(node: str) -> Path:
    if not CLI_ENTRY.is_file():
        raise CursorSdkError(f"Cursor SDK runner missing at {CLI_ENTRY}")
    tsx = PACKAGE_DIR / "node_modules" / "tsx" / "dist" / "cli.mjs"
    if tsx.is_file() and (PACKAGE_DIR / "node_modules" / "@cursor" / "sdk").exists():
        return tsx
    npm = shutil.which("npm")
    if not npm:
        raise CursorSdkError("npm is required to install scripts/cursor-sdk dependencies.")
    proc = subprocess.run(
        [npm, "install", "--no-fund", "--no-audit"],
        cwd=PACKAGE_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise CursorSdkError(
            "Failed to install @cursor/sdk. "
            f"npm exit {proc.returncode}: {(proc.stderr or proc.stdout).strip()[:800]}"
        )
    if not tsx.is_file():
        raise CursorSdkError("tsx did not install; cannot launch the Cursor SDK runner.")
    return tsx


def run_request(
    request: Mapping[str, Any],
    *,
    json_output: bool = False,
    runner: Any = None,
) -> int:
    """Launch the TypeScript runner. ``runner`` is the test seam (inject a fake)."""
    if runner is not None:
        return int(runner(request, json_output=json_output))
    try:
        node = find_node()
        tsx = ensure_package(node)
    except CursorSdkError as exc:
        print(str(exc), file=sys.stderr)
        return _EXIT_STARTUP
    argv = [node, str(tsx), str(CLI_ENTRY), "--request-json", "-"]
    if json_output:
        argv.append("--json")
    env = os.environ.copy()
    # Credential is already in the JSON body; keep env for the SDK's own fallbacks
    # but the request always carries apiKey explicitly.
    env["CURSOR_API_KEY"] = str(request.get("apiKey") or "")
    proc = subprocess.run(
        argv,
        input=json.dumps(request),
        cwd=str(request.get("cwd") or os.getcwd()),
        env=env,
        text=True,
        encoding="utf-8",
    )
    return int(proc.returncode)


def persist_agent_id(agent_id: str | None) -> None:
    if not agent_id:
        return
    state_dir = Path(get_hermes_home()) / "cursor-sdk"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "last-agent.json").write_text(
        json.dumps({"agentId": agent_id}) + "\n", encoding="utf-8"
    )


def cmd_cursor_sdk(args: Any, *, runner: Any = None) -> int:
    if not getattr(args, "cursor_sdk_command", None):
        print(
            "usage: hermes cursor-sdk <prompt|send|resume|get|get-run|list> --local|--cloud …\n"
            "\n"
            "  prompt   One-shot Agent.prompt (SDK disposes for you)\n"
            "  send     Durable Agent.create + send (+ optional --follow-up)\n"
            "  resume   Agent.resume across process boundaries (re-pass MCP)\n"
            "  get      Inspect an agent by ID\n"
            "  get-run  Inspect a run by ID (not a bc- agent ID)\n"
            "  list     List agents for the selected runtime\n",
            file=sys.stderr,
        )
        return _EXIT_STARTUP
    try:
        request = build_request(args)
    except CursorSdkError as exc:
        print(str(exc), file=sys.stderr)
        return _EXIT_STARTUP
    code = run_request(request, json_output=bool(getattr(args, "json", False)), runner=runner)
    agent_id = request.get("agentId")
    if code == _EXIT_OK and request.get("pattern") in {"send", "resume"}:
        persist_agent_id(str(agent_id) if agent_id else None)
    return code

"""``hermes cursor-sdk`` — Cursor TypeScript SDK (prompt / create+send / resume)."""

from __future__ import annotations

from hermes_cli.subcommands._shared import add_json_flag


def _add_runtime_flags(parser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--local",
        action="store_true",
        help="Local runtime: AgentOptions.local.cwd (required unless --cloud)",
    )
    group.add_argument(
        "--cloud",
        action="store_true",
        help="Cloud runtime: AgentOptions.cloud.repos (required unless --local)",
    )
    parser.add_argument("--cwd", default=None, help="Local working directory (default: process cwd)")
    parser.add_argument("--repo", default=None, help="Cloud repo URL (required for cloud prompt/send/resume)")
    parser.add_argument("--ref", default=None, help="Cloud startingRef (default: config or main)")
    parser.add_argument("--model", default=None, help="Model id (default: composer-2)")
    parser.add_argument("--api-key", default=None, help="Cursor API key (else CURSOR_API_KEY)")
    parser.add_argument(
        "--mcp-json",
        default=None,
        help="JSON file of inline mcpServers (re-passed on resume; not persisted by the SDK)",
    )
    parser.add_argument(
        "--setting-sources",
        default=None,
        help="Comma-separated local.settingSources (default: empty — no ambient Cursor config)",
    )
    parser.add_argument(
        "--auto-create-pr",
        action="store_true",
        help="Cloud: open a PR when the agent finishes",
    )
    parser.add_argument(
        "--no-skip-reviewer-request",
        dest="skip_reviewer_request",
        action="store_false",
        default=None,
        help="Cloud: allow reviewer-request notifications (CI default is skip)",
    )
    parser.add_argument("--no-stream", action="store_true", help="Skip run.stream(); still wait()")
    parser.add_argument(
        "--cancel-after-ms",
        type=int,
        default=None,
        help="Cancel the live run after N milliseconds if run.supports('cancel')",
    )


def build_cursor_sdk_parser(subparsers) -> None:
    """Attach the ``cursor-sdk`` subcommand to ``subparsers``."""
    parser = subparsers.add_parser(
        "cursor-sdk",
        help="Run Cursor SDK agents (prompt, durable send, resume)",
        description=(
            "Production wrapper around @cursor/sdk. Always pass --local or --cloud. "
            "Exit 0 = finished, 1 = startup/CursorAgentError, 2 = run status error."
        ),
    )
    sub = parser.add_subparsers(dest="cursor_sdk_command")

    prompt_p = sub.add_parser("prompt", help="One-shot Agent.prompt (SDK disposes)")
    prompt_p.add_argument("prompt", nargs="+", help="Prompt text")
    _add_runtime_flags(prompt_p)
    add_json_flag(prompt_p, "Emit the structured InvocationResult as JSON")

    send_p = sub.add_parser("send", help="Durable Agent.create + send (+ optional follow-up)")
    send_p.add_argument("prompt", nargs="+", help="First prompt")
    send_p.add_argument(
        "--follow-up",
        action="append",
        default=[],
        help="In-process follow-up send() on the same agent (repeatable)",
    )
    _add_runtime_flags(send_p)
    add_json_flag(send_p, "Emit the structured InvocationResult as JSON")

    resume_p = sub.add_parser("resume", help="Agent.resume an existing agentId, then send")
    resume_p.add_argument("agent_id", help="Agent ID (bc- prefix = cloud)")
    resume_p.add_argument("prompt", nargs="+", help="Follow-up prompt")
    _add_runtime_flags(resume_p)
    add_json_flag(resume_p, "Emit the structured InvocationResult as JSON")

    get_p = sub.add_parser("get", help="Inspect an agent by ID")
    get_p.add_argument("agent_id", help="Agent ID")
    _add_runtime_flags(get_p)
    add_json_flag(get_p, "Emit JSON")

    get_run = sub.add_parser("get-run", help="Inspect a run by ID (not a bc- agent ID)")
    get_run.add_argument("run_id", help="Run ID (UUID; not bc-…)")
    get_run.add_argument("--agent-id", dest="agent_id", default=None, help="Parent cloud agent ID")
    _add_runtime_flags(get_run)
    add_json_flag(get_run, "Emit JSON")

    list_p = sub.add_parser("list", aliases=["ls"], help="List agents for the selected runtime")
    _add_runtime_flags(list_p)
    add_json_flag(list_p, "Emit JSON")

    def _dispatch(args):
        from hermes_cli.cursor_sdk_cmd import cmd_cursor_sdk

        action = getattr(args, "cursor_sdk_command", None)
        if action == "ls":
            args.cursor_sdk_command = "list"
        return cmd_cursor_sdk(args)

    parser.set_defaults(func=_dispatch)

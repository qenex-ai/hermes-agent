"""Invariant tests for ``hermes cursor-sdk`` request routing.

These assert the Python seam (pattern, explicit runtime, bc- vs run ID, MCP
re-pass, follow-up send) without talking to Cursor or reading TypeScript
source. The TypeScript suite in ``scripts/cursor-sdk`` covers dispose and
SDK exit codes against a fake Agent.
"""
from __future__ import annotations

import argparse

import pytest

from hermes_cli.cursor_sdk_cmd import (
    CLOUD_AGENT_PREFIX,
    CursorSdkError,
    build_request,
    cmd_cursor_sdk,
)


@pytest.fixture
def hermes_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CURSOR_API_KEY", "cursor_test_key")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _ns(**over):
    defaults = dict(
        cursor_sdk_command="prompt",
        prompt=["hello"],
        local=True,
        cloud=False,
        cwd=None,
        repo=None,
        ref=None,
        model=None,
        api_key=None,
        mcp_json=None,
        setting_sources=None,
        auto_create_pr=False,
        skip_reviewer_request=None,
        no_stream=False,
        cancel_after_ms=None,
        follow_up=[],
        agent_id=None,
        run_id=None,
        json=False,
    )
    defaults.update(over)
    return argparse.Namespace(**defaults)


def test_prompt_send_resume_routing(hermes_env, tmp_path):
    prompt = build_request(_ns(cursor_sdk_command="prompt", prompt=["one", "shot"]))
    assert prompt["pattern"] == "prompt"
    assert prompt["prompt"] == "one shot"
    assert "followUps" not in prompt
    assert prompt["runtime"] == "local"
    assert prompt["cwd"] == str(tmp_path)
    assert prompt["settingSources"] == []
    assert prompt["apiKey"] == "cursor_test_key"
    assert prompt["model"] == "composer-2"

    send = build_request(
        _ns(
            cursor_sdk_command="send",
            prompt=["find the bug"],
            follow_up=["write a regression test"],
        )
    )
    assert send["pattern"] == "send"
    assert send["followUps"] == ["write a regression test"]

    resume = build_request(
        _ns(
            cursor_sdk_command="resume",
            agent_id="agt_prev",
            prompt=["continue"],
        )
    )
    assert resume["pattern"] == "resume"
    assert resume["agentId"] == "agt_prev"


def test_explicit_runtime_required_and_cloud_options(hermes_env, tmp_path):
    with pytest.raises(CursorSdkError, match="explicit"):
        build_request(_ns(local=False, cloud=False))
    with pytest.raises(CursorSdkError, match="not both"):
        build_request(_ns(local=True, cloud=True))

    cloud = build_request(
        _ns(
            local=False,
            cloud=True,
            repo="https://github.com/org/repo",
            ref="main",
        )
    )
    assert cloud["runtime"] == "cloud"
    assert cloud["repos"] == [{"url": "https://github.com/org/repo", "startingRef": "main"}]
    assert cloud["skipReviewerRequest"] is True
    assert cloud["autoCreatePR"] is False


def test_get_run_rejects_cloud_agent_id(hermes_env):
    with pytest.raises(CursorSdkError, match="not a run ID"):
        build_request(
            _ns(
                cursor_sdk_command="get-run",
                prompt=[],
                run_id=f"{CLOUD_AGENT_PREFIX}abc123",
                local=False,
                cloud=True,
                repo="https://github.com/org/repo",
                agent_id=f"{CLOUD_AGENT_PREFIX}abc123",
            )
        )


def test_resume_repasses_mcp_json(hermes_env, tmp_path):
    mcp_path = tmp_path / "mcp.json"
    mcp_path.write_text(
        '{"linear": {"type": "http", "url": "https://mcp.example/sse"}}',
        encoding="utf-8",
    )
    req = build_request(
        _ns(
            cursor_sdk_command="resume",
            agent_id="agt_prev",
            prompt=["again"],
            mcp_json=str(mcp_path),
        )
    )
    assert req["mcpServers"]["linear"]["url"] == "https://mcp.example/sse"


def test_cmd_exit_codes_and_pattern_via_injected_runner(hermes_env, capsys):
    seen = {}

    def fake_runner(request, json_output=False):
        seen["request"] = dict(request)
        seen["json"] = json_output
        return 2

    args = _ns(cursor_sdk_command="send", prompt=["go"], json=True)
    assert cmd_cursor_sdk(args, runner=fake_runner) == 2
    assert seen["request"]["pattern"] == "send"
    assert seen["json"] is True

    args = argparse.Namespace(cursor_sdk_command=None)
    assert cmd_cursor_sdk(args, runner=fake_runner) == 1
    err = capsys.readouterr().err
    assert "hermes cursor-sdk" in err

    assert cmd_cursor_sdk(_ns(local=False, cloud=False), runner=fake_runner) == 1


def test_missing_api_key_is_startup_error(hermes_env, monkeypatch):
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    with pytest.raises(CursorSdkError, match="CURSOR_API_KEY"):
        build_request(_ns())


def test_argparse_routes_prompt_send_resume_and_list_alias(hermes_env):
    import argparse as ap

    from hermes_cli.subcommands.cursor_sdk import build_cursor_sdk_parser

    parser = ap.ArgumentParser()
    build_cursor_sdk_parser(parser.add_subparsers())

    prompt = parser.parse_args(["cursor-sdk", "prompt", "hello", "world", "--local"])
    assert prompt.cursor_sdk_command == "prompt"
    assert prompt.local is True
    req = build_request(prompt)
    assert req["pattern"] == "prompt"
    assert req["prompt"] == "hello world"

    send = parser.parse_args(
        ["cursor-sdk", "send", "find it", "--local", "--follow-up", "write a test"]
    )
    assert send.cursor_sdk_command == "send"
    assert build_request(send)["followUps"] == ["write a test"]

    resume = parser.parse_args(
        ["cursor-sdk", "resume", "agt_1", "continue", "--cloud", "--repo", "https://github.com/o/r"]
    )
    assert resume.cursor_sdk_command == "resume"
    rreq = build_request(resume)
    assert rreq["agentId"] == "agt_1"
    assert rreq["runtime"] == "cloud"

    listed = parser.parse_args(["cursor-sdk", "ls", "--local"])
    assert listed.cursor_sdk_command == "ls"
    assert build_request(listed)["pattern"] == "list"

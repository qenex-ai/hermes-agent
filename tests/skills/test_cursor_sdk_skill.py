"""Behavior contracts for the cursor-sdk skill (CLI + three SDK patterns)."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO / "skills" / "software-development" / "cursor-sdk" / "SKILL.md"
RUNNER = REPO / "scripts" / "cursor-sdk" / "src" / "cli.ts"


def _frontmatter_and_body():
    content = SKILL_PATH.read_text(encoding="utf-8")
    assert content.startswith("---")
    m = re.search(r"\n---\s*\n", content[3:])
    assert m, "frontmatter must close"
    fm = yaml.safe_load(content[3 : m.start() + 3])
    body = content[m.end() + 3 :]
    return fm, body


def test_skill_and_runner_exist():
    assert SKILL_PATH.is_file()
    assert RUNNER.is_file()
    assert (REPO / "hermes_cli" / "cursor_sdk_cmd.py").is_file()


def test_frontmatter_contract():
    fm, _ = _frontmatter_and_body()
    assert fm["name"] == "cursor-sdk"
    desc = fm["description"]
    assert len(desc) <= 60
    assert desc.endswith(".")
    assert fm["platforms"]


def test_skill_documents_three_patterns_and_terminal():
    _, body = _frontmatter_and_body()
    assert "`terminal`" in body
    assert "hermes cursor-sdk prompt" in body
    assert "hermes cursor-sdk send" in body
    assert "hermes cursor-sdk resume" in body
    assert "Agent.prompt" in body
    assert "Agent.create" in body
    assert "Agent.resume" in body
    assert "--local" in body and "--cloud" in body
    assert "CURSOR_API_KEY" in body
    assert "bc-" in body

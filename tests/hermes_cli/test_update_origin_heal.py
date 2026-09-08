"""Restore a missing ``origin`` remote from a sibling remote before ``hermes update`` fetches.

Production (Sep 2026): ``git fetch origin`` died with
``fatal: 'origin' does not appear to be a git repository`` on checkouts that
still had ``upstream`` (or a fork remote) after origin was deleted. The updater
must copy an already-configured URL onto ``origin`` — never invent Nous or a
fork host — and prefer a hermes-agent fork over official ``upstream``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from hermes_cli import update_cmd


OFFICIAL = "https://github.com/NousResearch/hermes-agent.git"
FORK = "https://github.com/example/hermes-agent.git"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    return repo


class TestCandidateOriginFromRemotes:
    def test_prefers_hermes_fork_over_official_upstream(self):
        picked = update_cmd._candidate_origin_from_remotes(
            [
                ("upstream", OFFICIAL),
                ("fork", FORK),
            ]
        )
        assert picked == ("fork", FORK)

    def test_sole_upstream_is_used_when_that_is_all_that_remains(self):
        picked = update_cmd._candidate_origin_from_remotes([("upstream", OFFICIAL)])
        assert picked == ("upstream", OFFICIAL)

    def test_ambiguous_non_hermes_remotes_are_not_guessed(self):
        picked = update_cmd._candidate_origin_from_remotes(
            [
                ("heroku", "https://git.heroku.com/app.git"),
                ("gitlab", "https://gitlab.com/org/other.git"),
            ]
        )
        assert picked is None

    def test_does_not_invent_a_url_when_no_remotes_remain(self):
        assert update_cmd._candidate_origin_from_remotes([]) is None


def test_ensure_origin_remote_restores_from_upstream(tmp_path, capsys):
    """Invariant: a repo with only ``upstream`` gets ``origin`` pointing at that same URL."""
    repo = _init_repo(tmp_path)
    _git(repo, "remote", "add", "upstream", OFFICIAL)
    assert _git(repo, "remote") == "upstream"

    url = update_cmd._ensure_origin_remote(["git"], repo)
    assert url == OFFICIAL
    assert _git(repo, "remote", "get-url", "origin") == OFFICIAL
    out = capsys.readouterr().out
    assert "restored from 'upstream'" in out
    assert OFFICIAL in out

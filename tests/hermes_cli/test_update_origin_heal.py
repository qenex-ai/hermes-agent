"""Restore a missing ``origin`` remote before ``hermes update`` fetches.

Production (Sep 2026): ``git fetch origin`` died with
``fatal: 'origin' does not appear to be a git repository``. Recovery order:
sibling remotes (fork over official ``upstream``) → last URL this install used
→ official Nous, and only when no sibling remotes remain. The picker itself
never invents a URL. Fork hosts are never hardcoded.
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

    def test_config_regexp_lines_keep_stored_urls(self):
        from hermes_cli.update_cmd_git import _parse_remote_config_urls
        pairs = _parse_remote_config_urls(
            "remote.upstream.url https://github.com/NousResearch/hermes-agent.git\n"
            "remote.fork.url https://github.com/example/hermes-agent.git\n"
        )
        assert pairs == [
            ("upstream", OFFICIAL),
            ("fork", FORK),
        ]


def test_ensure_origin_remote_restores_from_upstream(tmp_path, capsys):
    """Invariant: a repo with only ``upstream`` gets ``origin`` pointing at that same URL."""
    repo = _init_repo(tmp_path)
    _git(repo, "remote", "add", "upstream", OFFICIAL)
    assert _git(repo, "remote") == "upstream"

    url = update_cmd._ensure_origin_remote(["git"], repo)
    stored = _git(repo, "config", "--get", "remote.origin.url")
    assert stored == OFFICIAL
    assert url == OFFICIAL
    assert "origin" in _git(repo, "remote").split()
    out = capsys.readouterr().out
    assert "restored from 'upstream'" in out
    assert OFFICIAL in out


def test_unusable_origin_url_is_replaced_from_upstream(tmp_path, capsys):
    """A leftover origin URL that is not a git repo must not skip restore."""
    repo = _init_repo(tmp_path)
    _git(repo, "remote", "add", "origin", "not-a-git-repo")
    _git(repo, "remote", "add", "upstream", OFFICIAL)
    url = update_cmd._ensure_origin_remote(["git"], repo)
    assert url == OFFICIAL
    assert _git(repo, "config", "--get", "remote.origin.url") == OFFICIAL
    assert "reset from 'upstream'" in capsys.readouterr().out


def test_zero_remotes_recalls_last_known(tmp_path, capsys):
    """Invariant: a wiped-remotes checkout recovers the last origin this install used."""
    from hermes_constants import get_hermes_home

    repo = _init_repo(tmp_path)
    cache = Path(get_hermes_home()) / ".update_origin_url"
    cache.write_text(FORK + "\n", encoding="utf-8")
    url = update_cmd._ensure_origin_remote(["git"], repo)
    assert url == FORK
    assert _git(repo, "config", "--get", "remote.origin.url") == FORK
    assert "last successful update" in capsys.readouterr().out


def test_successful_restore_writes_last_known(tmp_path):
    """Next wipe can only recall a URL this install previously restored."""
    from hermes_constants import get_hermes_home

    repo = _init_repo(tmp_path)
    _git(repo, "remote", "add", "upstream", OFFICIAL)
    update_cmd._ensure_origin_remote(["git"], repo)
    cache = Path(get_hermes_home()) / ".update_origin_url"
    assert cache.read_text(encoding="utf-8").strip() == OFFICIAL


def test_zero_remotes_last_resort_official(tmp_path, capsys):
    """A checkout with no remotes and no cache still gets a fetchable origin."""
    repo = _init_repo(tmp_path)
    url = update_cmd._ensure_origin_remote(["git"], repo)
    assert url == OFFICIAL
    assert _git(repo, "config", "--get", "remote.origin.url") == OFFICIAL
    out = capsys.readouterr().out
    assert "official Hermes repository" in out
    assert "point origin back at it" in out


def test_ambiguous_non_hermes_remotes_do_not_invent_official(tmp_path):
    """Invariant: leftover non-hermes remotes are not replaced with Nous."""
    repo = _init_repo(tmp_path)
    _git(repo, "remote", "add", "heroku", "https://git.heroku.com/app.git")
    _git(repo, "remote", "add", "gitlab", "https://gitlab.com/org/other.git")
    assert update_cmd._ensure_origin_remote(["git"], repo) is None
    assert "origin" not in _git(repo, "remote").split()


def test_origin_url_looks_fetchable_rejects_garbage(tmp_path):
    from hermes_cli.update_cmd_git import _origin_url_looks_fetchable

    assert _origin_url_looks_fetchable(OFFICIAL)
    assert _origin_url_looks_fetchable("git@github.com:NousResearch/hermes-agent.git")
    assert not _origin_url_looks_fetchable("")
    assert not _origin_url_looks_fetchable("not-a-git-repo")
    empty = tmp_path / "empty-dir"
    empty.mkdir()
    assert not _origin_url_looks_fetchable(str(empty))
    repo = _init_repo(tmp_path)
    assert _origin_url_looks_fetchable(str(repo))


def test_local_non_git_origin_is_replaced_with_official(tmp_path, capsys):
    """An origin URL that exists on disk but is not a git repo must not be kept."""
    junk = tmp_path / "not-a-repo"
    junk.mkdir()
    repo = _init_repo(tmp_path)
    _git(repo, "remote", "add", "origin", str(junk))
    url = update_cmd._ensure_origin_remote(["git"], repo)
    assert url == OFFICIAL
    assert _git(repo, "config", "--get", "remote.origin.url") == OFFICIAL
    assert "official Hermes repository" in capsys.readouterr().out


def test_fetch_by_url_creates_origin_ref_when_remote_is_gone(tmp_path, monkeypatch):
    """Invariant: `git fetch <url> branch:refs/remotes/origin/<branch>` unsticks
    a checkout that cannot `git fetch origin`."""
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init")
    (src / "readme").write_text("ok\n", encoding="utf-8")
    _git(src, "-c", "user.email=t@t", "-c", "user.name=t", "add", "readme")
    _git(src, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init")
    branch = _git(src, "rev-parse", "--abbrev-ref", "HEAD")
    dest = _init_repo(tmp_path)

    monkeypatch.setattr(update_cmd, "_ensure_origin_remote", lambda *a, **k: None)
    monkeypatch.setattr(
        "hermes_cli.update_cmd_git._recalled_origin_url", lambda: str(src)
    )

    result = update_cmd._fetch_origin_branch(["git"], dest, branch)
    assert result.returncode == 0
    assert _git(dest, "rev-parse", "--verify", f"origin/{branch}")
    assert _git(dest, "config", "--get", "remote.origin.url") == str(src)

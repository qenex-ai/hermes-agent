"""Regression tests for the parked-branch guard in ``hermes update``.

Live incident (2026-08-17, Teknium's Linux box): the source checkout was
parked on a stale feature branch (``claude-code-inspired/local-terminal-
memory-limit``, days behind main) left there by earlier tooling. ``hermes
update`` autostashed, refreshed lazy backends, synced skills and printed
"✓ Code updated!" / "✓ Update complete!" — while the checkout stayed on the
stale branch with none of main's new code. Two sessions burned time on
"the fix is missing" confusion that was really this.

The guard (``_assess_parked_branch_switch``):
- clean tree + branch fully merged into origin/<target>  → safe to
  auto-switch back to the target (and STAY there — no switch-back).
- clean tree + unmerged commits → still switch (loud 'kept' notice);
  non-interactive callers cannot resolve a skip.
- dirty tree → stash on the parked branch, switch, park the stash
  (never restore onto the update target). Skipping forever stranded
  HermesAction/cron retries.
- git failure, or ``updates.auto_switch_parked_branch: false`` → do
  NOT touch the branch; warn loudly and mark the code update SKIPPED.

These tests run the guard against REAL git repositories (init, commit,
branch, clone) — not mocked subprocess.run — so they exercise the actual
``git status`` / ``git cherry`` semantics the guard depends on.
"""

import subprocess
from types import SimpleNamespace

import pytest

from hermes_cli import main as hermes_main
import hermes_cli.main_web_build as main_web_build
import hermes_cli.main_install_repair as main_install_repair
from hermes_cli import update_cmd


GIT = ["git"]


def _git(cwd, *args, check=True):
    return subprocess.run(
        GIT + list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


@pytest.fixture()
def repo_pair(tmp_path):
    """A real origin repo + local clone, with main two commits ahead of the
    clone's parked state.

    Returns (clone_path,). The clone starts parked on feature branch
    ``old-feature`` cut from the first commit; origin/main has moved on.
    """
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    _git(origin, "config", "user.email", "test@example.com")
    _git(origin, "config", "user.name", "Test")
    (origin / "a.txt").write_text("one\n")
    _git(origin, "add", "a.txt")
    _git(origin, "commit", "-qm", "c1")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "Test")
    # Park the clone on a feature branch cut at c1.
    _git(clone, "checkout", "-qb", "old-feature")

    # main advances upstream (two commits).
    (origin / "a.txt").write_text("two\n")
    _git(origin, "commit", "-aqm", "c2")
    (origin / "b.txt").write_text("three\n")
    _git(origin, "add", "b.txt")
    _git(origin, "commit", "-qm", "c3")

    _git(clone, "fetch", "-q", "origin", "main")
    return clone


@pytest.fixture(autouse=True)
def _no_config(monkeypatch):
    """Isolate the guard from the machine's real config.yaml."""
    import hermes_cli.config as hermes_config

    monkeypatch.setattr(hermes_config, "load_config", lambda: {})


# ---------------------------------------------------------------------------
# _assess_parked_branch_switch against real repos
# ---------------------------------------------------------------------------

def test_clean_fully_merged_branch_is_safe_to_switch(repo_pair):
    """Parked branch == ancestor of origin/main, clean tree → auto-switch."""
    safe, reason = update_cmd._assess_parked_branch_switch(
        GIT, repo_pair, "old-feature", "main"
    )
    assert safe is True
    assert reason == ""


def test_dirty_tree_is_not_a_silent_switch(repo_pair):
    """Uncommitted changes on the parked branch → assessor reports dirty
    (the guard stashes then switches; it must not pretend the tree is clean)."""
    (repo_pair / "a.txt").write_text("local edit\n")
    safe, reason = update_cmd._assess_parked_branch_switch(
        GIT, repo_pair, "old-feature", "main"
    )
    assert safe is False
    assert reason == "dirty"


def test_untracked_file_blocks_auto_switch(repo_pair):
    """Untracked files count as dirty too — they'd ride along on checkout."""
    (repo_pair / "scratch.py").write_text("wip\n")
    safe, reason = update_cmd._assess_parked_branch_switch(
        GIT, repo_pair, "old-feature", "main"
    )
    assert safe is False
    assert reason == "dirty"


def test_unmerged_commits_switch_with_kept_notice(repo_pair):
    """Commits on the parked branch not in origin/main: still safe to switch
    (checkout keeps them on the branch) — reason carries the count so the
    caller prints the loud 'kept' notice. Non-interactive callers (desktop
    update button, gateway /update, cron) depend on this: they cannot
    resolve a skip."""
    (repo_pair / "feature.txt").write_text("unmerged work\n")
    _git(repo_pair, "add", "feature.txt")
    _git(repo_pair, "commit", "-qm", "feature work")

    safe, reason = update_cmd._assess_parked_branch_switch(
        GIT, repo_pair, "old-feature", "main"
    )
    assert safe is True
    assert reason == "unmerged:1"


def test_equivalent_cherry_picked_commit_is_still_safe(repo_pair):
    """A commit whose patch already landed upstream (git cherry '-') does
    not block the switch — only genuinely unmerged '+' commits do."""
    # Cherry-pick origin/main's c2 onto the parked branch: patch-identical.
    _git(repo_pair, "cherry-pick", "origin/main~1")
    safe, reason = update_cmd._assess_parked_branch_switch(
        GIT, repo_pair, "old-feature", "main"
    )
    assert safe is True
    assert reason == ""


def test_config_opt_out_blocks_auto_switch(repo_pair, monkeypatch):
    """updates.auto_switch_parked_branch: false disables auto-switch even
    when the branch is clean and merged."""
    import hermes_cli.config as hermes_config

    monkeypatch.setattr(
        hermes_config,
        "load_config",
        lambda: {"updates": {"auto_switch_parked_branch": False}},
    )
    safe, reason = update_cmd._assess_parked_branch_switch(
        GIT, repo_pair, "old-feature", "main"
    )
    assert safe is False
    assert reason == "disabled"


def test_missing_origin_ref_is_unverifiable(repo_pair):
    """If origin/<target> can't be resolved, the guard refuses to switch."""
    safe, reason = update_cmd._assess_parked_branch_switch(
        GIT, repo_pair, "old-feature", "no-such-branch"
    )
    assert safe is False
    assert reason == "unverifiable"


# ---------------------------------------------------------------------------
# Skip warning content
# ---------------------------------------------------------------------------

def test_skip_warning_names_branch_behind_count_and_commands(repo_pair, capsys):
    update_cmd._print_parked_branch_skip_warning(
        GIT, repo_pair, "old-feature", "main", "dirty"
    )
    out = capsys.readouterr().out
    assert "CODE UPDATE SKIPPED" in out
    assert "old-feature" in out
    assert "2 commit(s) BEHIND" in out
    assert f"git -C {repo_pair} checkout main && hermes update" in out


def test_skip_warning_dirty_reason(repo_pair, capsys):
    update_cmd._print_parked_branch_skip_warning(
        GIT, repo_pair, "old-feature", "main", "dirty"
    )
    out = capsys.readouterr().out
    assert "uncommitted changes" in out


def test_dirty_notice_names_branch_and_stash_restore(capsys):
    update_cmd._print_parked_branch_dirty_notice("old-feature", "main")
    out = capsys.readouterr().out
    assert "parked on 'old-feature'" in out
    assert "uncommitted changes" in out
    assert "git checkout old-feature && git stash apply" in out
    assert "CODE UPDATE SKIPPED" not in out


def test_kept_notice_names_branch_count_and_recovery(capsys):
    update_cmd._print_parked_branch_kept_notice("old-feature", "main", "3")
    out = capsys.readouterr().out
    assert "parked on 'old-feature'" in out
    assert "3 commit(s) not merged into origin/main" in out
    assert "safe on 'old-feature'" in out
    assert "git checkout old-feature" in out
    assert "CODE UPDATE SKIPPED" not in out


# ---------------------------------------------------------------------------
# Summary branch/HEAD visibility
# ---------------------------------------------------------------------------

def test_branch_head_label_reflects_real_checkout(repo_pair):
    label = update_cmd._branch_head_label(GIT, repo_pair)
    short = _git(repo_pair, "rev-parse", "--short", "HEAD").stdout.strip()
    assert label == f"old-feature @ {short}"


def test_branch_head_label_detached(repo_pair):
    _git(repo_pair, "checkout", "-q", "--detach")
    label = update_cmd._branch_head_label(GIT, repo_pair)
    assert label is not None
    assert label.startswith("detached @ ")


def test_branch_head_suffix_empty_on_non_repo(tmp_path):
    assert update_cmd._branch_head_suffix(GIT, tmp_path / "not-a-repo") == ""


def test_print_update_completion_carries_branch_and_sha(
    repo_pair, monkeypatch, capsys
):
    monkeypatch.setattr(hermes_main, "PROJECT_ROOT", repo_pair)
    update_cmd._print_update_completion("✓ Update complete!")
    out = capsys.readouterr().out
    short = _git(repo_pair, "rev-parse", "--short", "HEAD").stdout.strip()
    assert f"✓ Update complete! [old-feature @ {short}]" in out


# ---------------------------------------------------------------------------
# Full update flow: parked branch dirty/unmerged → SKIPPED, no false success
# ---------------------------------------------------------------------------

def _patch_update_flow(monkeypatch, repo, run_real_git=True):
    """Point _cmd_update_impl at the real repo and neuter the long tail.

    Matches the monkeypatch surface of test_update_head_moved_gate.py, but
    keeps REAL subprocess.run so the git plumbing runs against the fixture
    repo (the whole point of these regressions).
    """
    monkeypatch.setattr(hermes_main, "PROJECT_ROOT", repo)
    monkeypatch.setattr(hermes_main, "_resolve_update_branch", lambda args: "main")
    monkeypatch.setattr(hermes_main, "_is_windows", lambda: False)
    monkeypatch.setattr(main_install_repair, "_is_windows", lambda: False)
    monkeypatch.setattr(
        hermes_main, "_get_origin_url",
        lambda *a, **k: "https://github.com/NousResearch/hermes-agent.git",
    )
    monkeypatch.setattr(update_cmd, "_is_fork", lambda *a, **k: False)
    monkeypatch.setattr(update_cmd, "_discard_lockfile_churn", lambda *a, **k: None)
    monkeypatch.setattr(update_cmd, "_discard_lockfile_churn", lambda *a, **k: None)
    monkeypatch.setattr(update_cmd, "_normalize_managed_eol", lambda *a, **k: None)
    monkeypatch.setattr(hermes_main, "_clear_bytecode_cache", lambda *a, **k: 0)
    monkeypatch.setattr(hermes_main, "_record_bytecode_fingerprint", lambda *a, **k: None)
    monkeypatch.setattr(main_web_build, "_record_bytecode_fingerprint", lambda *a, **k: None)
    monkeypatch.setattr(hermes_main, "_run_pre_update_backup", lambda *a, **k: None)
    monkeypatch.setattr(hermes_main, "_pause_windows_gateways_for_update", lambda: None)
    monkeypatch.setattr(
        hermes_main, "_resume_windows_gateways_after_update", lambda *a, **k: None
    )
    monkeypatch.setattr(hermes_main, "_capture_active_lazy_features", lambda: [])
    monkeypatch.setattr(hermes_main, "_capture_active_tool_dependencies", lambda: [])


def test_update_stashes_and_switches_dirty_parked_branch(
    repo_pair, monkeypatch, capsys
):
    """HermesAction / gateway / cron shape: parked branch + dirty tree.
    Skip forever is unrecoverable for non-interactive callers. Stash on the
    parked branch, switch to main, pull, and park the stash — never restore
    those edits onto main."""
    (repo_pair / "a.txt").write_text("local edit\n")
    _patch_update_flow(monkeypatch, repo_pair)

    class _StopFlow(Exception):
        pass

    monkeypatch.setattr(
        hermes_main,
        "_abort_dependency_sync_if_self_locked",
        lambda *a, **k: (_ for _ in ()).throw(_StopFlow()),
    )
    args = SimpleNamespace(branch=None, yes=False, force=False, force_venv=False)

    with pytest.raises(_StopFlow):
        hermes_main.cmd_update(args)

    out = capsys.readouterr().out
    assert "CODE UPDATE SKIPPED" not in out
    assert "uncommitted changes" in out
    assert "old-feature" in out
    assert "✓ Code updated!" not in out  # stopped before dep sync / completion
    assert (
        _git(repo_pair, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        == "main"
    )
    assert (repo_pair / "a.txt").read_text() == "two\n"
    assert (repo_pair / "b.txt").exists()
    stashes = _git(repo_pair, "stash", "list").stdout
    assert "hermes-update-autostash-" in stashes
    assert "local edit" in _git(repo_pair, "stash", "show", "-p").stdout


def test_update_stashes_untracked_files_on_dirty_parked_branch(
    repo_pair, monkeypatch, capsys
):
    """Untracked files count as dirty and must be stashed (--include-untracked),
    not ride along onto main."""
    (repo_pair / "scratch.py").write_text("wip\n")
    _patch_update_flow(monkeypatch, repo_pair)

    class _StopFlow(Exception):
        pass

    monkeypatch.setattr(
        hermes_main,
        "_abort_dependency_sync_if_self_locked",
        lambda *a, **k: (_ for _ in ()).throw(_StopFlow()),
    )
    args = SimpleNamespace(branch=None, yes=False, force=False, force_venv=False)

    with pytest.raises(_StopFlow):
        hermes_main.cmd_update(args)

    assert (
        _git(repo_pair, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        == "main"
    )
    assert not (repo_pair / "scratch.py").exists()
    assert "scratch.py" in _git(repo_pair, "stash", "show", "--include-untracked", "--name-only").stdout
    out = capsys.readouterr().out
    assert "CODE UPDATE SKIPPED" not in out


def test_update_still_skips_dirty_parked_when_auto_switch_disabled(
    repo_pair, monkeypatch, capsys
):
    """updates.auto_switch_parked_branch: false still skips — dirty stash-switch
    must not override an explicit opt-out."""
    import hermes_cli.config as hermes_config

    monkeypatch.setattr(
        hermes_config,
        "load_config",
        lambda: {"updates": {"auto_switch_parked_branch": False}},
    )
    (repo_pair / "a.txt").write_text("local edit\n")
    _patch_update_flow(monkeypatch, repo_pair)
    args = SimpleNamespace(branch=None, yes=False, force=False, force_venv=False)

    with pytest.raises(SystemExit) as exc_info:
        hermes_main.cmd_update(args)

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "CODE UPDATE SKIPPED" in out
    assert "auto_switch_parked_branch" in out
    assert (
        _git(repo_pair, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        == "old-feature"
    )
    assert (repo_pair / "a.txt").read_text() == "local edit\n"
    assert _git(repo_pair, "stash", "list").stdout.strip() == ""


def test_update_dirty_parked_stash_survives_discard_config(
    repo_pair, monkeypatch, capsys
):
    """updates.non_interactive_local_changes: discard is for local edits on
    the update target. Feature-branch WIP must stay parked in the stash."""
    import hermes_cli.config as hermes_config

    monkeypatch.setattr(
        hermes_config,
        "load_config",
        lambda: {"updates": {"non_interactive_local_changes": "discard"}},
    )
    (repo_pair / "a.txt").write_text("local edit\n")
    _patch_update_flow(monkeypatch, repo_pair)

    class _StopFlow(Exception):
        pass

    monkeypatch.setattr(
        hermes_main,
        "_abort_dependency_sync_if_self_locked",
        lambda *a, **k: (_ for _ in ()).throw(_StopFlow()),
    )
    args = SimpleNamespace(
        branch=None, yes=True, force=False, force_venv=False,
    )

    with pytest.raises(_StopFlow):
        hermes_main.cmd_update(args)

    out = capsys.readouterr().out
    assert "CODE UPDATE SKIPPED" not in out
    assert "Discarded local source changes" not in out
    assert (
        _git(repo_pair, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        == "main"
    )
    assert (repo_pair / "a.txt").read_text() == "two\n"
    assert "hermes-update-autostash-" in _git(repo_pair, "stash", "list").stdout
    assert "local edit" in _git(repo_pair, "stash", "show", "-p").stdout


def test_update_switches_unmerged_parked_branch_with_kept_notice(
    repo_pair, monkeypatch, capsys
):
    """Default strategy ("switch"): clean tree + unmerged commits → the
    update proceeds (non-interactive callers like the desktop update button
    cannot resolve a skip), prints the loud 'kept' notice, ends on main
    fast-forwarded to origin/main, and the commits stay on the parked
    branch untouched."""
    (repo_pair / "feature.txt").write_text("unmerged work\n")
    _git(repo_pair, "add", "feature.txt")
    _git(repo_pair, "commit", "-qm", "feature work")
    feature_sha = _git(repo_pair, "rev-parse", "old-feature").stdout.strip()
    _patch_update_flow(monkeypatch, repo_pair)

    class _StopFlow(Exception):
        pass

    monkeypatch.setattr(
        hermes_main,
        "_abort_dependency_sync_if_self_locked",
        lambda *a, **k: (_ for _ in ()).throw(_StopFlow()),
    )
    args = SimpleNamespace(branch=None, yes=False, force=False, force_venv=False)

    with pytest.raises(_StopFlow):
        hermes_main.cmd_update(args)

    out = capsys.readouterr().out
    assert "1 commit(s) not merged into origin/main" in out
    assert "safe on 'old-feature'" in out
    assert "CODE UPDATE SKIPPED" not in out
    assert "updating it in place" not in out
    # Ends on main, fast-forwarded.
    assert (
        _git(repo_pair, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        == "main"
    )
    head = _git(repo_pair, "rev-parse", "HEAD").stdout.strip()
    remote = _git(repo_pair, "rev-parse", "origin/main").stdout.strip()
    assert head == remote
    # The unmerged commit is still exactly where it was, on the branch.
    assert (
        _git(repo_pair, "rev-parse", "old-feature").stdout.strip()
        == feature_sha
    )


def test_update_updates_unmerged_branch_in_place_when_configured(
    repo_pair, monkeypatch, capsys
):
    """updates.parked_branch_strategy: update_in_place — a maintained custom
    branch (local patches on top of main) is updated in place from
    origin/<target> instead of switched away from. The running code must
    advance (origin/main's files arrive) AND the local commits must survive,
    with the checkout never moving."""
    import hermes_cli.config as hermes_config

    monkeypatch.setattr(
        hermes_config,
        "load_config",
        lambda: {"updates": {"parked_branch_strategy": "update_in_place"}},
    )
    (repo_pair / "feature.txt").write_text("unmerged work\n")
    _git(repo_pair, "add", "feature.txt")
    _git(repo_pair, "commit", "-qm", "feature work")
    _patch_update_flow(monkeypatch, repo_pair)

    # Stop right after the pull/branch logic, before dependency install.
    class _StopFlow(Exception):
        pass

    monkeypatch.setattr(
        hermes_main,
        "_abort_dependency_sync_if_self_locked",
        lambda *a, **k: (_ for _ in ()).throw(_StopFlow()),
    )
    args = SimpleNamespace(branch=None, yes=False, force=False, force_venv=False)

    with pytest.raises(_StopFlow):
        hermes_main.cmd_update(args)

    out = capsys.readouterr().out
    assert "updating it in place" in out
    assert "CODE UPDATE SKIPPED" not in out
    # The checkout never moved.
    assert (
        _git(repo_pair, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        == "old-feature"
    )
    # origin/main's code actually arrived (b.txt lands with c3)...
    assert (repo_pair / "b.txt").exists()
    assert (repo_pair / "a.txt").read_text() == "two\n"
    # ...and the branch's own commit survived it.
    assert (repo_pair / "feature.txt").read_text() == "unmerged work\n"
    assert "feature work" in _git(repo_pair, "log", "--oneline").stdout


def test_switch_branch_flag_overrides_in_place_strategy(
    repo_pair, monkeypatch, capsys
):
    """--switch-branch overrides updates.parked_branch_strategy:
    update_in_place for one run: the unmerged branch is LEFT ALONE and the
    update runs on the target instead.

    A long-lived feature branch does not want an update-driven merge commit
    in its history (#89507 review). The branch tip must be byte-identical
    afterwards, while the checkout ends up on the updated target.
    """
    import hermes_cli.config as hermes_config

    monkeypatch.setattr(
        hermes_config,
        "load_config",
        lambda: {"updates": {"parked_branch_strategy": "update_in_place"}},
    )
    (repo_pair / "feature.txt").write_text("unmerged work\n")
    _git(repo_pair, "add", "feature.txt")
    _git(repo_pair, "commit", "-qm", "feature work")
    branch_tip_before = _git(
        repo_pair, "rev-parse", "old-feature"
    ).stdout.strip()
    _patch_update_flow(monkeypatch, repo_pair)

    class _StopFlow(Exception):
        pass

    monkeypatch.setattr(
        hermes_main,
        "_abort_dependency_sync_if_self_locked",
        lambda *a, **k: (_ for _ in ()).throw(_StopFlow()),
    )
    args = SimpleNamespace(
        branch=None, yes=False, force=False, force_venv=False,
        switch_branch=True,
    )

    with pytest.raises(_StopFlow):
        hermes_main.cmd_update(args)

    out = capsys.readouterr().out
    assert "1 commit(s) not merged into origin/main" in out
    assert "updating it in place" not in out
    assert "CODE UPDATE SKIPPED" not in out
    # Checkout moved to the target and picked up its code...
    assert (
        _git(repo_pair, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        == "main"
    )
    assert (repo_pair / "b.txt").exists()
    # ...and the feature branch was not written to at all.
    assert (
        _git(repo_pair, "rev-parse", "old-feature").stdout.strip()
        == branch_tip_before
    )


def test_unmerged_branch_still_updates_in_place_without_the_flag(
    repo_pair, monkeypatch, capsys
):
    """--switch-branch is opt-in: with the in-place strategy configured and
    no flag, the update stays in place."""
    import hermes_cli.config as hermes_config

    monkeypatch.setattr(
        hermes_config,
        "load_config",
        lambda: {"updates": {"parked_branch_strategy": "update_in_place"}},
    )
    (repo_pair / "feature.txt").write_text("unmerged work\n")
    _git(repo_pair, "add", "feature.txt")
    _git(repo_pair, "commit", "-qm", "feature work")
    _patch_update_flow(monkeypatch, repo_pair)

    class _StopFlow(Exception):
        pass

    monkeypatch.setattr(
        hermes_main,
        "_abort_dependency_sync_if_self_locked",
        lambda *a, **k: (_ for _ in ()).throw(_StopFlow()),
    )
    args = SimpleNamespace(
        branch=None, yes=False, force=False, force_venv=False,
        switch_branch=False,
    )

    with pytest.raises(_StopFlow):
        hermes_main.cmd_update(args)

    out = capsys.readouterr().out
    assert "updating it in place" in out
    assert "--switch-branch" not in out
    assert (
        _git(repo_pair, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        == "old-feature"
    )


def test_update_auto_switches_clean_merged_parked_branch(
    repo_pair, monkeypatch, capsys
):
    """Clean + fully merged parked branch → auto-switch back to main, pull,
    say so, and STAY on main afterwards (sabotage-proven: reverting the
    guard re-parks the checkout and this test fails on the branch assert)."""
    _patch_update_flow(monkeypatch, repo_pair)
    # Stop the flow right after the pull/branch logic: the dependency
    # install phase begins with _abort_dependency_sync_if_self_locked.
    class _StopFlow(Exception):
        pass

    monkeypatch.setattr(
        hermes_main,
        "_abort_dependency_sync_if_self_locked",
        lambda *a, **k: (_ for _ in ()).throw(_StopFlow()),
    )
    args = SimpleNamespace(branch=None, yes=False, force=False, force_venv=False)

    with pytest.raises(_StopFlow):
        hermes_main.cmd_update(args)

    out = capsys.readouterr().out
    assert "parked on 'old-feature'" in out
    assert "fully merged" in out
    assert "switching back to main" in out
    assert "CODE UPDATE SKIPPED" not in out
    # The checkout ends up ON main, fast-forwarded to origin/main.
    assert (
        _git(repo_pair, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        == "main"
    )
    head = _git(repo_pair, "rev-parse", "HEAD").stdout.strip()
    remote = _git(repo_pair, "rev-parse", "origin/main").stdout.strip()
    assert head == remote


def test_update_up_to_date_path_does_not_repark_merged_branch(
    tmp_path, monkeypatch, capsys
):
    """commit_count == 0 path: before this fix, the updater switched BACK to
    the parked feature branch after checking main ("Restore stash and switch
    back to original branch") — silently re-parking the checkout so every
    subsequent update repeated the incident. A clean, fully merged parked
    branch must now END on main."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    _git(origin, "config", "user.email", "test@example.com")
    _git(origin, "config", "user.name", "Test")
    (origin / "a.txt").write_text("one\n")
    _git(origin, "add", "a.txt")
    _git(origin, "commit", "-qm", "c1")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "Test")
    _git(clone, "checkout", "-qb", "old-feature")
    # No new upstream commits: local main == origin/main == old-feature tip.

    _patch_update_flow(monkeypatch, clone)

    class _StopFlow(Exception):
        pass

    import hermes_cli.managed_uv as managed_uv

    monkeypatch.setattr(
        managed_uv,
        "update_managed_uv",
        lambda *a, **k: (_ for _ in ()).throw(_StopFlow()),
    )
    args = SimpleNamespace(branch=None, yes=False, force=False, force_venv=False)

    with pytest.raises(_StopFlow):
        hermes_main.cmd_update(args)

    out = capsys.readouterr().out
    assert "switched back to main" in out
    # The regression: old code ran `git checkout old-feature` here.
    assert (
        _git(clone, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"
    )


def test_update_up_to_date_dirty_parked_does_not_restore_onto_main(
    tmp_path, monkeypatch, capsys
):
    """commit_count == 0 + dirty parked branch: stash, switch to main, park
    the stash. Restoring those edits onto main is the failure class the
    original skip guarded."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    _git(origin, "config", "user.email", "test@example.com")
    _git(origin, "config", "user.name", "Test")
    (origin / "a.txt").write_text("one\n")
    _git(origin, "add", "a.txt")
    _git(origin, "commit", "-qm", "c1")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "Test")
    _git(clone, "checkout", "-qb", "old-feature")
    (clone / "a.txt").write_text("local edit\n")

    _patch_update_flow(monkeypatch, clone)

    class _StopFlow(Exception):
        pass

    import hermes_cli.managed_uv as managed_uv

    monkeypatch.setattr(
        managed_uv,
        "update_managed_uv",
        lambda *a, **k: (_ for _ in ()).throw(_StopFlow()),
    )
    args = SimpleNamespace(branch=None, yes=False, force=False, force_venv=False)

    with pytest.raises(_StopFlow):
        hermes_main.cmd_update(args)

    out = capsys.readouterr().out
    assert "CODE UPDATE SKIPPED" not in out
    assert "uncommitted changes" in out
    assert (
        _git(clone, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"
    )
    assert (clone / "a.txt").read_text() == "one\n"
    assert "hermes-update-autostash-" in _git(clone, "stash", "list").stdout
    assert "local edit" in _git(clone, "stash", "show", "-p").stdout


def test_update_on_main_fast_path_unchanged(repo_pair, monkeypatch, capsys):
    """On the target branch already: no guard prints, normal pull flow."""
    _git(repo_pair, "checkout", "-q", "main")

    _patch_update_flow(monkeypatch, repo_pair)

    class _StopFlow(Exception):
        pass

    monkeypatch.setattr(
        hermes_main,
        "_abort_dependency_sync_if_self_locked",
        lambda *a, **k: (_ for _ in ()).throw(_StopFlow()),
    )
    args = SimpleNamespace(branch=None, yes=False, force=False, force_venv=False)

    with pytest.raises(_StopFlow):
        hermes_main.cmd_update(args)

    out = capsys.readouterr().out
    assert "parked on" not in out
    assert "CODE UPDATE SKIPPED" not in out
    assert (
        _git(repo_pair, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        == "main"
    )
    head = _git(repo_pair, "rev-parse", "HEAD").stdout.strip()
    remote = _git(repo_pair, "rev-parse", "origin/main").stdout.strip()
    assert head == remote

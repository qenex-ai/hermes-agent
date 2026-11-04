"""Update dependency diagnostics, historical markers and Windows launcher recovery."""

import logging
import os
import shutil
import subprocess
import sys
import time as _time

from pathlib import Path
from typing import NoReturn
from hermes_cli import _early_recovery as _early_recovery_mod

# Log-record parity with the origin module.
logger = logging.getLogger("hermes_cli.main")


def _pyproject_project(debug_fmt: str | None = None) -> dict | None:
    """``[project]`` table of pyproject.toml, or ``None`` when absent/unreadable."""
    from hermes_cli.main import PROJECT_ROOT
    pyproject = PROJECT_ROOT / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        import tomllib
        with pyproject.open("rb") as handle:
            project = tomllib.load(handle).get("project", {})
    except Exception as exc:
        if debug_fmt:
            logger.debug(debug_fmt, exc)
        return None
    return project if isinstance(project, dict) else None


# Install-scoped breadcrumbs live next to the venv (not under $HERMES_HOME)
# because the venv is shared across profiles.
#   ``.update-incomplete``       — generic core ``.[all]`` install was interrupted;
#     cleared only after a confirmed full dependency reinstall/recovery.
#   ``.lazy-refresh-incomplete`` — lazy-backend refresh may have corrupted packages;
#     cleared only after import-probe repair confirms healthy (never on indeterminate).
# Narrow lazy probes must NEVER clear the generic core marker.
# See #58004.
def _update_marker_path() -> Path:
    from hermes_cli.main import PROJECT_ROOT
    return PROJECT_ROOT / ".update-incomplete"


def _lazy_refresh_marker_path() -> Path:
    from hermes_cli.main import PROJECT_ROOT
    return PROJECT_ROOT / ".lazy-refresh-incomplete"


def _pytest_owns_live_checkout(root: Path) -> bool:
    """True under pytest when ``root`` is this checkout: unsandboxed update/recovery tests must
    neither litter the live repo root with breadcrumbs (false-arming the developer's next launch)
    nor run a real reinstall against the executing venv (cf. ``managed_scope._under_pytest``)."""
    return "PYTEST_CURRENT_TEST" in os.environ and root == Path(__file__).resolve().parent.parent


def _clear_marker_file(path: Path, *, label: str) -> None:
    """Remove an update-recovery breadcrumb. Never raises."""
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.debug("Could not clear %s marker: %s", label, exc)


def _clear_update_incomplete_marker() -> None:
    """Remove the interrupted core-install breadcrumb. Never raises."""
    _clear_marker_file(_update_marker_path(), label="update-incomplete")


def _clear_lazy_refresh_incomplete_marker() -> None:
    """Remove the interrupted lazy-refresh breadcrumb. Never raises."""
    _clear_marker_file(_lazy_refresh_marker_path(), label="lazy-refresh-incomplete")


# Frozen old-updater import; current updates never detach dependency work.
_UPDATE_REEXEC_ENV = "HERMES_UPDATE_REEXEC"


def _reexec_dependency_sync_off_windows_shim() -> NoReturn:
    """Stop a mixed old-code/new-files updater at the retired sync boundary."""
    from hermes_cli._old_updater import stop_for_relaunch
    stop_for_relaunch()


def _is_windows() -> bool:
    return sys.platform == "win32"


def _venv_scripts_dir() -> Path | None:
    """Return the venv Scripts directory if we're running inside the project venv."""
    from hermes_cli.main import PROJECT_ROOT
    from hermes_constants import project_venv_dir
    from pm.environments import venv_bin_dir
    venv_dir = project_venv_dir(PROJECT_ROOT)
    if venv_dir is None:
        return None
    scripts = venv_bin_dir(venv_dir, windows=_is_windows())
    return scripts if scripts.is_dir() else None


def _hermes_exe_shims(scripts_dir: Path) -> list[Path]:
    """Entry-point shims uv may rewrite during ``pip install -e .`` — Windows .exe launchers
    only; POSIX shims are plain scripts replaced atomically."""
    if not _is_windows():
        return []
    names = set(_load_console_script_names()) or {"hermes", "hermes-agent", "hermes-acp"}
    # Not a [project.scripts] entry point, but older update/install paths still
    # rewrite and quarantine it.
    names.add("hermes-gateway")
    return [scripts_dir / f"{name}.exe" for name in sorted(names)]


_PENDING_RENAME_KEY = r"SYSTEM\CurrentControlSet\Control\Session Manager"
_PENDING_RENAME_VALUE = "PendingFileRenameOperations"


def _filter_pending_shim_renames(entries: list[str], shims: list[Path]) -> tuple[list[str], int]:
    """Drop our ``<shim>`` -> ``<shim>.old.<stamp>`` pairs from a PendingFileRenameOperations
    value (a flat REG_MULTI_SZ of (source, target) pairs shared with other installers).
    Returns the entries to keep and how many pairs were dropped."""
    import ntpath

    def _norm(value: str) -> str:
        path = str(value).lstrip("!")
        path = path.removeprefix("\\??\\")
        return ntpath.normcase(ntpath.normpath(path))

    shim_paths = {_norm(str(shim)) for shim in shims}
    kept: list[str] = []
    removed = 0
    for index in range(0, len(entries) - 1, 2):
        source, target = entries[index], entries[index + 1]
        source_norm = _norm(source)
        if source_norm in shim_paths and _norm(target).startswith(f"{source_norm}.old."):
            removed += 1
        else:
            kept.extend((source, target))
    if len(entries) % 2:
        kept.append(entries[-1])
    return kept, removed


def _cleanup_pending_shim_renames(scripts_dir: Path) -> int:
    """Drop reboot renames older Hermes versions queued for our shims: ``MOVEFILE_DELAY_UNTIL_REBOOT``
    fallbacks outlive the update that queued them and move away whatever sits at the shim path
    at next boot — even a shim a later repair just wrote. Needs elevation; a no-op otherwise."""
    if not _is_windows():
        return 0
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, _PENDING_RENAME_KEY, 0,
            winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE,
        ) as key:
            entries, value_type = winreg.QueryValueEx(key, _PENDING_RENAME_VALUE)
            if value_type != winreg.REG_MULTI_SZ or not isinstance(entries, list):
                return 0
            kept, removed = _filter_pending_shim_renames(entries, _hermes_exe_shims(scripts_dir))
            if not removed:
                return 0
            if kept:
                winreg.SetValueEx(key, _PENDING_RENAME_VALUE, 0, winreg.REG_MULTI_SZ, kept)
            else:
                winreg.DeleteValue(key, _PENDING_RENAME_VALUE)
            return removed
    except (OSError, ValueError):
        return 0


# Fresh orphan files can belong to an updater still running.
_QUARANTINE_GRACE_SECONDS = 15 * 60


def _quarantine_stamp_ms(stale: Path) -> int | None:
    """The ``.old.<unix-ms>`` stamp in a quarantine filename; ``None`` (not ours — neither rescued
    nor deleted) otherwise. Parsed from the NAME, not ``st_mtime``: ``rename`` preserves the
    shim's mtime (when uv wrote it), not when it was quarantined."""
    try:
        return int(stale.name.rsplit(".old.", 1)[1])
    except (IndexError, ValueError):
        return None


def _recover_update_debts_on_startup() -> None:
    """The startup half of a previous update, run on every launch before dispatch."""
    # Dependency recovery already ran before imports. Report any fleet restart
    # still owed by a previous update without restarting services here.
    if "update" not in sys.argv[1:]:
        try:
            from hermes_cli.update_cmd_fleet import _warn_pending_fleet_restart_on_startup

            _warn_pending_fleet_restart_on_startup()
        except Exception:  # a startup warning never blocks the launch it warns about
            logger.debug("pending fleet restart check failed", exc_info=True)
    from hermes_cli.update_pause_record import recover as _recover_paused_gateways
    # Unconditional: recover() itself skips the PARSED `update`/`gateway run` commands; a raw argv
    # value equal to "update" (`--resume update`) is no reason to strand paused gateways.
    _recover_paused_gateways()  # a killed `hermes update` left gateways paused (Windows)


def _cleanup_quarantined_exes(scripts_dir: Path | None = None) -> None:
    """Sweep — and where necessary RESCUE — ``hermes.exe.old.*`` from updates.

    Called early on every invocation. Two cases an unconditional ``unlink()`` gets wrong:
    (1) orphan rescue — ``hermes.exe`` missing while ``hermes.exe.old.*`` exists means the .old
    file is the ONLY surviving copy (update died between rename and uv's write); put it back via
    the same retry-and-report helper the update-time restore uses. (2) concurrency — a fresh
    quarantine file may belong to an update in flight in another process; leave anything inside
    the grace window alone. Silent no-op on non-Windows, nothing to do, or locked/permission errors.

    Deleting it converts a one-rename recovery into a full reinstall. See #75584.
    """
    if not _is_windows():
        return
    scripts_dir = scripts_dir if scripts_dir is not None else _venv_scripts_dir()
    if scripts_dir is None:
        return
    from hermes_cli.main import PROJECT_ROOT
    from hermes_cli.update_lock import update_in_progress

    if update_in_progress(PROJECT_ROOT):
        return  # every quarantine may be that update's own, mid rename-back
    _cleanup_pending_shim_renames(scripts_dir)
    now = _time.time()
    try:
        candidates = [
            (stamp, stale) for stale in scripts_dir.glob("*.exe.old.*")
            if (stamp := _quarantine_stamp_ms(stale)) is not None]
    except OSError:
        return
    # Newest first by PARSED stamp: lexicographic order breaks when a stray ``.old.999`` exists.
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    for stamp, stale in candidates:
        try:
            original = stale.with_name(stale.name.rsplit(".old.", 1)[0])
            if not original.exists():
                # Orphan rescue: last copy of the shim — retry ladder + recovery message.
                _early_recovery_mod.restore_quarantined_shims([(original, stale)])
                continue
            if now - stamp / 1000.0 < _QUARANTINE_GRACE_SECONDS:
                continue  # may be a live quarantine from a concurrent update
            stale.unlink()
        except OSError:
            pass  # still locked or in use — try again next run


def _configured_features_missing_deps() -> list[tuple[str, str, str]]:
    """Check configured platforms/MCP in the fresh, selected update-build child.

    PM preserves recorded extras atomically, but configuration can reference an
    unselected SDK. Never call this in the updater's stale import graph (#10651).
    Rows are ``(label, hint, candidate extra)``: a platform's SDK is the extra named after it.
    """
    missing: list[tuple[str, str, str]] = []
    try:
        from gateway.config import load_gateway_config
        from gateway.platform_registry import platform_registry

        for platform in load_gateway_config().get_connected_platforms():
            entry = platform_registry.get(platform.value)
            if entry is not None and not entry.check_fn():
                missing.append((entry.label, entry.install_hint or "Run `hermes setup` to install support.",
                                entry.name))
    except Exception as exc:
        logger.debug("configured-platform dependency check skipped: %s", exc)
    try:
        import importlib.util
        from hermes_cli.config import load_config_readonly

        if (load_config_readonly().get("mcp_servers") or {}) and importlib.util.find_spec("mcp") is None:
            missing.append(("MCP servers", "Run `hermes pm install` to install MCP support.", "mcp"))
    except Exception as exc:
        logger.debug("configured-MCP dependency check skipped: %s", exc)
    return missing


def _install_configured_features_missing_deps(project_root: Path) -> None:
    """Add the extras configured features need to the dependency environment (#124228).

    Recorded extras never follow config, so an enabled platform whose SDK is not
    selected would come up without its adapter after the gateway restart.
    """
    import pm
    from pm.extras import declined_extras, extra_supported
    from pm.features import declared_extras

    missing = _configured_features_missing_deps()
    if not missing:
        return
    # `hermes pm install --without NAME` outranks a platform still left in config.
    declared = set(declared_extras(project_root)) - declined_extras(project_root)
    extras = sorted({extra for *_, name in missing
                     if (extra := name.replace("_", "-")) in declared and extra_supported(extra)})
    if extras:
        try:
            # Config asked for these, not the user: a `--without` landing before the PM lock still wins.
            pm.sync_venv(extras, explicit=True, project_root=project_root, evict_incompatible_plugins=True,
                         automatic=extras)
        except Exception as exc:
            print(f"  ⚠ Could not install {', '.join(extras)} for configured features: {exc}")
        else:
            installed = set(extras) - declined_extras(project_root)
            missing = [row for row in missing if row[2].replace("_", "-") not in installed]
    if missing:
        print("  ⚠ Configured features whose dependencies are still missing — the gateway will fail to load them on restart:")
        for feature, hint, _extra in missing:
            print(f"    - {feature}: {hint}")


def _load_console_script_names() -> list[str]:
    """Return ``[project.scripts]`` entry-point names from pyproject.toml."""
    project = _pyproject_project("console script verification: failed to read pyproject.toml: %s")
    scripts = (project or {}).get("scripts", {}) or {}
    return [str(name) for name in scripts if name]


def _is_termux_env(env: dict[str, str] | None = None) -> bool:
    from hermes_cli.main import _is_termux_startup_environment
    return _is_termux_startup_environment(env)


def _is_windows_npm_path(npm_path: str) -> bool:
    """True if ``npm_path`` points at a Windows npm shim (WSL drive interop, ``.cmd``/``.exe``, UNC).

    Callers use this only on a POSIX host — on native Windows ``npm.cmd`` is correct.
    """
    low = npm_path.lower()
    mount = low.split("/", 3)[2] if low.startswith("/mnt/") else ""
    return (
        low.endswith((".exe", ".cmd", ".bat"))
        or (len(mount) == 1 and mount.isalpha())
        or "\\" in npm_path
    )


def _resolve_node_runtime_npm() -> str | None:
    """PM's npm, refused on a POSIX host when it is a Windows shim (EISDIR over WSL UNC paths, #30271).

    Never re-scans the user's PATH for another npm: Hermes runs only its PM-managed toolchain.
    """
    from hermes_constants import find_node_executable
    npm = find_node_executable("npm")
    if _is_windows() or not npm:
        return npm
    return None if _is_windows_npm_path(npm) else npm


def _resolve_update_branch(args) -> str:
    """Normalize ``args.branch`` to a non-empty name (default ``main``; blank/whitespace = default)."""
    return (getattr(args, "branch", None) or "main").strip() or "main"


def _run_quarantined_install(
    cmd: list[str], *, env: dict[str, str] | None = None, scripts_dir: Path | None = None,
    strict_quarantine: bool = False,
) -> None:
    """Run an editable install, quarantining the running ``hermes.exe`` first.

    Every editable install rewrites the entry-point shims; on Windows the live ``hermes.exe``
    can be neither deleted nor overwritten, so without quarantine ``hermes`` drops off PATH.
    ``strict_quarantine=True`` (the update dependency sync): a shim whose rename failed every
    retry proves a hard venv hold — the install WILL hit the same lock on .pyd files — so roll
    back and raise :class:`ShimQuarantineError` without installing. Non-strict callers already
    mutated the venv, so refusing buys nothing. ``scripts_dir is None`` is a pass-through.

    See #87331.
    """
    moved: list[tuple[Path, Path]] = []
    failed: list[str] = []
    if scripts_dir is not None:
        moved = _quarantine_running_hermes_exe(scripts_dir, failed_out=failed)
    if strict_quarantine and failed:
        _restore_quarantined_exes(moved)
        raise ShimQuarantineError(failed)
    try:
        _run_install_with_heartbeat(cmd, env=env)
    finally:
        # Restore on FAILURE and SUCCESS: an already-satisfied editable install is a uv no-op
        # that rewrites no entry points. Skips shims the installer replaced; finally re-raises.
        if scripts_dir is not None:
            _restore_quarantined_exes(moved)


# A quarantine file younger than this may belong to an update running RIGHT NOW in
# another process, whose restore step still needs it — the only copy of that shim.
# Restore shims when the installer didn't write replacements — on FAILURE (install died before the
# entry-points step) and on SUCCESS too: uv audits an already-satisfied editable install as a no-op and
# rewrites no entry points, which would otherwise leave the shims quarantined aside and `hermes` missing
# from PATH after a green install (#75584). _restore_quarantined_exes skips any shim the installer actually
# replaced, so this never clobbers fresh output. Errors are not swallowed — the finally re-raises whatever
# escaped.
_QUARANTINE_GRACE_SECONDS = 15 * 60


def _verify_console_scripts_installed(
    install_cmd_prefix: list[str], *, env: dict[str, str] | None = None) -> None:
    """Ensure every declared console_script shim exists on disk after install.

    On Windows ``uv pip install -e .`` can register ``hermes.exe`` in the wheel RECORD while the
    file never lands (live shim locked, launcher write skipped), so ``hermes`` drops off PATH
    after a "successful" install. Missing shims get ``--reinstall -e .`` under quarantine.

    The symptom is ``hermes-agent.exe`` and ``hermes-acp.exe`` present but ``hermes.exe`` missing, so
    ``hermes`` drops off PATH even though the install reported success (issue #52931).
    """
    if not _is_windows():
        return
    scripts_dir = _venv_scripts_dir()
    names = _load_console_script_names() if scripts_dir is not None else []
    if not names:
        return

    def _missing() -> list[str]:
        return [name for name in names if not (scripts_dir / f"{name}.exe").is_file()]

    missing = _missing()
    if not missing:
        return
    print(
        f"  ⚠ Verification: {len(missing)} console script(s) missing on disk: "
        f"{', '.join(missing)}")
    print("  → Reinstalling entry points with --reinstall...")
    if not _run_repair_step(
        _run_quarantined_install, install_cmd_prefix + ["install", "--reinstall", "-e", "."],
        env=env, scripts_dir=scripts_dir,
        log_msg="console script verification: repair install failed: %s",
        fail_msg=(
            "  ⚠ Entry point repair failed; try `hermes update --force` after "
            "closing other hermes processes.")):
        return
    _report_still_missing(
        _missing(), "Workaround: python -m hermes_cli.main <command>",
        ok="  ✓ All console entry points restored")


def _verify_core_dependencies_installed(
    install_cmd_prefix: list[str], *, env: dict[str, str] | None = None, group: str = "all"
) -> None:
    """Check that every base dep from pyproject.toml is installed in the target venv; if not, retry.

    Reads ``pyproject.toml`` directly (not the venv's stale metadata), drops deps whose ``;``
    markers don't apply here, and probes ``importlib.metadata.version()`` in the venv
    interpreter. Missing deps trigger a base-group ``--reinstall``, then a per-package force
    install. The final state is a warning, not a hard failure, so one broken-on-PyPI dep can't
    block an otherwise-successful update — but the partial install is visible where it happened.
    """
    project = _pyproject_project("dep verification: failed to read pyproject.toml: %s")
    if project is None:
        return
    raw_deps = project.get("dependencies", []) or []
    applicable = _applicable_dependency_names(raw_deps)
    if not applicable:
        return
    # Probe inside the venv Python — sys.executable may be the outer Python that drove
    # ``hermes update``; the install prefix/env encode which environment we targeted.
    venv_python = _resolve_install_target_python(install_cmd_prefix, env)
    if venv_python is None:
        return

    def _missing_deps() -> list[str]:
        try:
            result = _venv_probe(venv_python, _MISSING_DEPS_SCRIPT, *applicable, env=env)
        except Exception as e:
            logger.debug("dep verification: subprocess failed: %s", e)
            return []
        return _nonblank_lines(result.stdout)

    missing = _missing_deps()
    if not missing:
        return
    print(
        f"  ⚠ Verification: {len(missing)} declared dep(s) missing after install: "
        f"{', '.join(missing[:8])}{'...' if len(missing) > 8 else ''}")
    print("  → Reinstalling base group with --reinstall to repair...")
    # Base group only, not ``[{group}]``: the missing dep is a *base* dep and the all-extras
    # install costs minutes. Quarantine first: ``--reinstall -e .`` rewrites the shims.
    scripts_dir = _venv_scripts_dir() if _is_windows() else None
    if not _run_repair_step(
        _run_quarantined_install, install_cmd_prefix + ["install", "--reinstall", "-e", "."],
        env=env, scripts_dir=scripts_dir,
        log_msg="dep verification: repair install failed: %s",
        fail_msg="  ⚠ Repair install failed; check `hermes update` output above."):
        return
    still_missing = _missing_deps()
    if not still_missing:
        print("  ✓ All declared core dependencies now installed")
        return
    # Last-ditch: install each remaining missing dep with its pin directly — uv's
    # resolver can think the env is satisfied while on-disk metadata disagrees.
    name_to_spec = dict(_naive_requirement(spec) for spec in raw_deps)
    specs = [name_to_spec.get(n, n) for n in still_missing]
    print(f"  → Force-installing remaining missing dep(s): {', '.join(specs)}")
    if not _run_repair_step(
        _run_install_with_heartbeat, install_cmd_prefix + ["install", "--reinstall", *specs],
        env=env,
        log_msg="dep verification: per-package repair failed: %s",
        fail_msg=(
            f"  ⚠ Could not install: {', '.join(still_missing)}. "
            "Run `hermes update --force` after closing other hermes processes.")):
        return
    _report_still_missing(
        _missing_deps(), "Run `hermes update --force` after closing other hermes processes.",
        ok="  ✓ All declared core dependencies now installed")


def _install_python_dependencies_with_optional_fallback(
    install_cmd_prefix: list[str], *, env: dict[str, str] | None = None, group: str = "all"
) -> None:
    """Install base deps plus as many optional extras as the environment supports.

    Targets ``.[all]`` by default; Termux callers pass ``group='termux-all'``. On Windows every
    attempt quarantines the live ``hermes*.exe`` shims first. When ``env`` carries a
    ``VIRTUAL_ENV`` that does not exist (pip / site-packages install), ``uv pip`` fails with
    ``Failed to inspect Python interpreter from active virtual environment`` before doing any
    work — pin the install at the running interpreter instead.

    Pin the install at the running interpreter instead so the update/recovery path succeeds on those
    installs (#71510 fixed the ZIP path, #83335 fixed lazy-deps; this closes the shared helper for the
    remaining callers).
    """
    scripts_dir = _venv_scripts_dir() if _is_windows() else None

    # Only uv needs the explicit pin; pip resolves the target from sys.executable itself.
    pin_python = bool(
        env and env.get("VIRTUAL_ENV") and not Path(env["VIRTUAL_ENV"]).is_dir()
        and install_cmd_prefix and _is_uv_command(install_cmd_prefix))
    if pin_python:
        env = {**env}
        env.pop("VIRTUAL_ENV", None)
        # Pinned to sys.executable, the shims uv rewrites live in THAT interpreter's Scripts
        # dir, not PROJECT_ROOT/venv; quarantining the wrong dir leaves hermes.exe locked.
        if scripts_dir is None and _is_windows():
            scripts_dir = _interpreter_scripts_dir()

    def _install(args: list[str]) -> None:
        if pin_python:
            args = _insert_python_pin(args)
        # strict_quarantine: this is the UPDATE dependency sync; ShimQuarantineError propagates
        # to the sync boundary, which defers via the update-incomplete marker instead.
        # A shim that cannot be renamed aside proves a hard venv hold; running uv anyway is how installs
        # strand half-updated (#87331).
        _run_quarantined_install(
            install_cmd_prefix + args, env=env, scripts_dir=scripts_dir, strict_quarantine=True)

    try:
        _install(["install", "-e", f".[{group}]"])
        _verify_console_scripts_installed(install_cmd_prefix, env=env)
        return
    except subprocess.CalledProcessError as exc:
        from hermes_cli._install_repair import (
            _INDEX_UNREACHABLE_NOTICE,
            install_failure_is_index_unreachable,
        )
        if install_failure_is_index_unreachable(exc):
            print(_INDEX_UNREACHABLE_NOTICE)
            raise
        print(
            "  ⚠ Optional extras failed, reinstalling base dependencies and retrying extras individually..."
        )

    _install(["install", "-e", "."])
    failed_extras: list[str] = []
    installed_extras: list[str] = []
    for extra in _load_installable_optional_extras(group=group):
        try:
            _install(["install", "-e", f".[{extra}]"])
            installed_extras.append(extra)
        except subprocess.CalledProcessError:
            failed_extras.append(extra)
    if installed_extras:
        print(f"  ✓ Reinstalled optional extras individually: {', '.join(installed_extras)}")
    if failed_extras:
        print(f"  ⚠ Skipped optional extras that still failed: {', '.join(failed_extras)}")
        _warn_configured_features_missing_deps(install_cmd_prefix, env=env)
    # uv's incremental resolver has left newly added base deps silently missing on a half-stale
    # venv, surfacing hours later as a downstream ModuleNotFoundError. Verify here instead.
    _verify_core_dependencies_installed(install_cmd_prefix, env=env, group=group)
    _verify_console_scripts_installed(install_cmd_prefix, env=env)


_CONFIGURED_FEATURES_SCRIPT = (
    "import importlib.util\n"
    "try:\n"
    "    from gateway.config import load_gateway_config\n"
    "    from gateway.platform_registry import platform_registry\n"
    "    for platform in load_gateway_config().get_connected_platforms():\n"
    "        entry = platform_registry.get(platform.value)\n"
    "        if entry is not None and not entry.check_fn():\n"
    "            print(entry.label + '\\t' + (entry.install_hint or 'reinstall the %r extra' % platform.value))\n"
    "except Exception:\n"
    "    pass\n"
    "try:\n"
    "    from hermes_cli.config import load_config\n"
    "    if (load_config().get('mcp_servers') or {}) and importlib.util.find_spec('mcp') is None:\n"
    "        print('MCP servers\\tinstall the ' + repr('mcp') + ' extra')\n"
    "except Exception:\n"
    "    pass\n"
)

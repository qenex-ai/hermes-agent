"""Skip the extras-fallback ladder when the package index is unreachable.

Production (Aug 2026): ``uv pip install -e .[all]`` timed out talking to
``pypi.org/simple/...`` (~45s, 3 retries). The updater then retried base + each
extra against the same dead index (~45s more). When captured output (or a
short probe) shows the index is down, re-raise immediately — do not ZIP-fallback
and do not claim the update succeeded.
"""

from __future__ import annotations

import subprocess

from hermes_cli import _install_repair as ir
from hermes_cli import main_install_repair


PYPI_TIMEOUT = (
    "error: Request failed after 3 retries in 45.1s\n"
    "  Caused by: Failed to fetch: `https://pypi.org/simple/pillow/`\n"
    "  Caused by: error sending request for url (https://pypi.org/simple/pillow/)\n"
    "  Caused by: client error (Connect)\n"
    "  Caused by: operation timed out\n"
)


def test_pypi_connect_timeout_is_index_unreachable():
    assert ir._output_is_index_unreachable(PYPI_TIMEOUT)
    exc = subprocess.CalledProcessError(
        2, ["uv", "pip", "install", "-e", ".[all]"], stderr=PYPI_TIMEOUT
    )
    assert ir.install_failure_is_index_unreachable(exc)


def test_compile_error_is_not_index_unreachable():
    blob = "error: failed to build `cryptography`\n  cargo rustc failed"
    assert not ir._output_is_index_unreachable(blob)
    exc = subprocess.CalledProcessError(
        1, ["uv", "pip", "install", "-e", ".[all]"], stderr=blob
    )
    assert not ir.install_failure_is_index_unreachable(exc)


def test_optional_extras_fallback_skipped_when_pypi_times_out(monkeypatch):
    """Invariant: a PyPI connect timeout must not start a second install against the same index."""
    calls: list[list[str]] = []

    def boom(cmd, *, env=None, scripts_dir=None, strict_quarantine=False):
        calls.append(list(cmd))
        raise subprocess.CalledProcessError(
            2, cmd, stderr=PYPI_TIMEOUT
        )

    monkeypatch.setattr(main_install_repair, "_run_quarantined_install", boom)
    monkeypatch.setattr(main_install_repair, "_venv_scripts_dir", lambda: None)

    try:
        main_install_repair._install_python_dependencies_with_optional_fallback(
            ["uv", "pip"]
        )
    except subprocess.CalledProcessError as exc:
        assert exc.returncode == 2
    else:
        raise AssertionError("expected the original install failure to propagate")

    assert len(calls) == 1
    assert calls[0][-2:] == ["-e", ".[all]"]


def test_early_recovery_skips_uv_when_index_unreachable(tmp_path, monkeypatch, capsys):
    """Invariant: a down package index must not spend ~45s in uv on every launch."""
    from hermes_cli import _early_recovery as er
    from hermes_cli import _install_repair as ir

    marker = tmp_path / ".update-incomplete"
    marker.write_text('{"attempts": 0}\n', encoding="utf-8")
    ran = []
    monkeypatch.setattr(ir, "_probe_index_unreachable", lambda timeout=3.0: True)
    monkeypatch.setattr(ir, "run_core_install", lambda root: ran.append(root))
    monkeypatch.setattr(er, "_claim_recovery_lock", lambda root: True)
    monkeypatch.setattr(er, "_release_recovery_lock", lambda root: None)
    monkeypatch.setattr(er, "_read_marker_attempts", lambda path: 0)

    assert er._complete_pending_core_install(tmp_path, marker) is False
    assert ran == []
    assert marker.exists()
    err = capsys.readouterr().err
    assert "Package index unreachable" in err

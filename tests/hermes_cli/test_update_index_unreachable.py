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

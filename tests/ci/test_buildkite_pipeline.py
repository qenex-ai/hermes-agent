"""Contracts for the Buildkite pipeline generator.

The GitHub Actions orchestrator remains the merge gate. Buildkite must still
honor the same two invariants the Linux pytest lane encodes: the canonical
runner, and no live API credentials in the job env.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "buildkite_pipeline.py"
_spec = importlib.util.spec_from_file_location("buildkite_pipeline", _PATH)
if _spec is None or _spec.loader is None:
    raise ImportError("Failed to load buildkite_pipeline.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_CLASSIFY_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "classify_changes.py"
_cspec = importlib.util.spec_from_file_location("classify_changes", _CLASSIFY_PATH)
if _cspec is None or _cspec.loader is None:
    raise ImportError("Failed to load classify_changes.py")
_cmod = importlib.util.module_from_spec(_cspec)
_cspec.loader.exec_module(_cmod)

emit_steps = _mod.emit_steps
collect_commands = _mod.collect_commands
pipeline_env = _mod.pipeline_env
classify = _cmod.classify


def test_fail_open_uses_canonical_runner_and_blanks_api_keys():
    """Push / empty-diff fail-open must run the same Linux gate GitHub does."""
    lanes = classify([])
    commands = collect_commands(emit_steps(lanes))
    joined = "\n".join(commands)
    assert "scripts/run_tests.sh" in joined
    assert "ruff check" in joined
    assert "uv lock --check" in joined
    assert "uv sync --locked" in joined
    assert "run-workspace-checks.mjs" in joined
    # nvm's install.sh exits 3 in non-interactive CI after printing
    # "Close and reopen your terminal"; the JS lane must not invoke it.
    assert "nvm-sh/nvm" not in joined
    assert "nodejs.org/dist/latest-v" in joined
    env = pipeline_env()
    assert env["OPENROUTER_API_KEY"] == ""
    assert env["OPENAI_API_KEY"] == ""
    assert env["NOUS_API_KEY"] == ""
    pytest_env = None
    for step in emit_steps(lanes):
        nested = step.get("steps") or []
        for child in nested:
            if child.get("key") == "pytest":
                pytest_env = child.get("env")
    assert pytest_env is not None
    assert pytest_env["OPENROUTER_API_KEY"] == ""
    assert pytest_env["OPENAI_API_KEY"] == ""
    assert pytest_env["NOUS_API_KEY"] == ""


def test_docs_only_diff_skips_python_and_js_lanes():
    """A prose-only change must not pay for pytest / ruff / npm ci."""
    lanes = classify(["README.md", "docs/guide.md"])
    commands = collect_commands(emit_steps(lanes))
    joined = "\n".join(commands)
    assert "scripts/run_tests.sh" not in joined
    assert "ruff check" not in joined
    assert "uv lock --check" not in joined
    assert "run-workspace-checks.mjs" not in joined
    assert "scripts/check-case-collisions.py" in joined

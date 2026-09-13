"""Invariants for scripts/ci/vercel_deploy.py.

The Vercel GitHub Actions path must keep three contracts:

1. Pull requests never get ``--prod``; production events always pass
   ``--prebuilt`` plus ``--prod``. That is the preview/promote split.
2. The token never appears on argv (process listings). Missing any of
   the three secrets must skip the deploy rather than call Vercel.
3. The CLI spec is a pinned ``vercel@X.Y.Z``, never ``latest``/``canary``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "vercel_deploy.py"
_spec = importlib.util.spec_from_file_location("vercel_deploy", _PATH)
if _spec is None or _spec.loader is None:
    raise ImportError("Failed to load vercel_deploy.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def _has_token_flag(argv: list[str]) -> bool:
    return any(arg == "--token" or arg.startswith("--token=") for arg in argv)


def test_preview_and_production_argv_contract():
    """PR → preview without --prod; main/release → production with --prod.

    Both paths are prebuilt, cwd-scoped to website/, and pull uses --yes
    so CI cannot hang on a prompt. The CLI spec stays a pinned major.minor.patch.
    """
    assert _mod.resolve_environment("pull_request", "refs/heads/feat") == "preview"
    assert (
        _mod.resolve_environment(
            "pull_request", "refs/heads/feat", dispatch_environment="production"
        )
        == "preview"
    )
    assert _mod.resolve_environment("push", "refs/heads/main") == "production"
    assert _mod.resolve_environment("release", "refs/tags/v1.0.0") == "production"
    assert _mod.resolve_environment("workflow_dispatch", "refs/heads/feat") == "production"
    assert (
        _mod.resolve_environment(
            "workflow_dispatch", "refs/heads/feat", dispatch_environment="preview"
        )
        == "preview"
    )

    preview_deploy = _mod.deploy_argv("preview")
    prod_deploy = _mod.deploy_argv("production")
    assert "--prebuilt" in preview_deploy
    assert "--prebuilt" in prod_deploy
    assert "--yes" in preview_deploy and "--yes" in prod_deploy
    assert "--prod" not in preview_deploy
    assert "--prod" in prod_deploy
    assert "--prod" not in _mod.build_argv("preview")
    assert "--prod" in _mod.build_argv("production")
    assert "--cwd" in preview_deploy and _mod.WEBSITE_CWD in preview_deploy

    pull = _mod.pull_argv("preview")
    assert pull[:3] == ["vercel", "pull", "--yes"]
    assert "--environment=preview" in pull

    spec = _mod.install_cli_spec()
    assert spec.startswith("vercel@")
    assert "latest" not in spec and "canary" not in spec
    version = spec.split("@", 1)[1]
    assert version[0].isdigit() and "." in version

    for argv in (preview_deploy, prod_deploy, pull, _mod.build_argv("production")):
        assert not _has_token_flag(argv)


def test_credentials_and_token_flag_never_reach_vercel(monkeypatch):
    """Skip when any secret is missing; refuse --token even if a caller adds it."""
    full = {
        "VERCEL_TOKEN": "tok",
        "VERCEL_ORG_ID": "org",
        "VERCEL_PROJECT_ID": "proj",
    }
    assert _mod.credentials_ready(full) is True
    assert _mod.credentials_ready({**full, "VERCEL_TOKEN": "  "}) is False
    assert _mod.credentials_ready({k: v for k, v in full.items() if k != "VERCEL_ORG_ID"}) is False

    monkeypatch.setattr(
        _mod.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not spawn vercel")),
    )
    with pytest.raises(ValueError, match="environment"):
        _mod.run_vercel(["vercel", "deploy", "--prebuilt", "--token", "leaked"])
    with pytest.raises(ValueError, match="environment"):
        _mod.run_vercel(["vercel", "deploy", "--token=leaked"])

    body = _mod.preview_comment_body(url="https://example.vercel.app", sha="abcdef1234")
    assert _mod.PREVIEW_COMMENT_MARKER in body
    assert "https://example.vercel.app" in body
    assert "abcdef1" in body

#!/usr/bin/env python3
"""Vercel prebuilt-deploy helpers for GitHub Actions.

The docs site lives in ``website/`` and needs Python generators (skills
pages, llms.txt) before ``docusaurus build``. Vercel's git-integration
rebuild and the old deploy-hook POST both run that build on Vercel's
builders, which do not have those generators. GitHub Actions does, so CI
runs ``vercel pull`` → ``vercel build`` → ``vercel deploy --prebuilt``.

Auth is ``VERCEL_TOKEN`` in the process environment. Putting
``--token`` on the argv leaks into process listings; ``run_vercel``
refuses that flag.

Usage (from the repo root, after checkout + Node + the pinned CLI):

    python3 scripts/ci/vercel_deploy.py gate
    python3 scripts/ci/vercel_deploy.py pull
    python3 scripts/ci/vercel_deploy.py build
    python3 scripts/ci/vercel_deploy.py deploy
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence

PINNED_VERCEL_CLI = "59.13.1"
WEBSITE_CWD = "website"
PREVIEW_COMMENT_MARKER = "<!-- hermes-vercel-preview -->"
_CREDENTIAL_KEYS = ("VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID")


def install_cli_spec() -> str:
    """npm package spec for the CLI. Never ``latest`` / ``canary``."""
    return f"vercel@{PINNED_VERCEL_CLI}"


def credentials_ready(environ: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return all((env.get(key) or "").strip() for key in _CREDENTIAL_KEYS)


def resolve_environment(
    event_name: str,
    ref: str,
    *,
    dispatch_environment: str = "",
) -> str:
    """Map a GitHub event to the Vercel target.

    Pull requests always preview (even if an input asks for production).
    ``main`` pushes, published releases, and workflow_dispatch default to
    production. An explicit ``preview`` dispatch stays preview. Other
    events preview so a later trigger widening cannot alias production.
    """
    explicit = (dispatch_environment or "").strip().lower()
    if explicit in {"production", "preview"}:
        if event_name == "pull_request" and explicit == "production":
            return "preview"
        return explicit
    event = (event_name or "").strip()
    ref = (ref or "").strip()
    if event == "pull_request":
        return "preview"
    if event == "release":
        return "production"
    if event in {"push", "workflow_dispatch"} and ref in {
        "refs/heads/main",
        "main",
    }:
        return "production"
    if event == "workflow_dispatch":
        return "production"
    return "preview"


def resolve_environment_from_env(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    explicit = (
        env.get("VERCEL_DEPLOY_ENVIRONMENT")
        or env.get("INPUT_ENVIRONMENT")
        or ""
    )
    return resolve_environment(
        env.get("GITHUB_EVENT_NAME", ""),
        env.get("GITHUB_REF", ""),
        dispatch_environment=explicit,
    )


def pull_argv(environment: str) -> list[str]:
    return [
        "vercel",
        "pull",
        "--yes",
        f"--environment={environment}",
        "--cwd",
        WEBSITE_CWD,
    ]


def build_argv(environment: str) -> list[str]:
    args = ["vercel", "build", "--cwd", WEBSITE_CWD]
    if environment == "production":
        args.append("--prod")
    return args


def deploy_argv(environment: str) -> list[str]:
    args = [
        "vercel",
        "deploy",
        "--prebuilt",
        "--yes",
        "--cwd",
        WEBSITE_CWD,
    ]
    if environment == "production":
        args.append("--prod")
    return args


def _reject_token_flag(argv: Sequence[str]) -> None:
    if any(arg == "--token" or arg.startswith("--token=") for arg in argv):
        raise ValueError(
            "VERCEL_TOKEN must come from the environment, not argv "
            "(process listings would leak it)"
        )


def run_vercel(
    argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    capture_stdout: bool = False,
) -> str:
    """Run a vercel argv. Never pass ``--token``.

    ``capture_stdout`` is for ``vercel deploy``, whose last stdout line is
    the deployment URL (progress goes to stderr).
    """
    _reject_token_flag(argv)
    merged = dict(os.environ if env is None else env)
    proc = subprocess.run(
        list(argv),
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture_stdout else None,
        env=merged,
    )
    if proc.returncode != 0:
        if capture_stdout and proc.stdout:
            sys.stderr.write(proc.stdout)
        raise SystemExit(proc.returncode)
    if not capture_stdout:
        return ""
    lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def preview_comment_body(*, url: str, sha: str) -> str:
    url = (url or "").strip()
    sha = (sha or "").strip()
    short = sha[:7] if sha else "unknown"
    return (
        f"{PREVIEW_COMMENT_MARKER}\n"
        "## Vercel Preview\n\n"
        f"- **URL**: {url}\n"
        "- **Target**: preview\n"
        f"- **Commit**: `{short}`\n\n"
        "Visit the preview URL to verify. Production deploys run from "
        "`main` or a published release.\n"
    )


def write_github_output(pairs: Mapping[str, str]) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    payload = "".join(f"{key}={value}\n" for key, value in pairs.items())
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(payload)
    else:
        sys.stdout.write(payload)


def _cmd_gate() -> int:
    ready = credentials_ready()
    environment = resolve_environment_from_env()
    write_github_output(
        {
            "can_deploy": "true" if ready else "false",
            "environment": environment,
        }
    )
    if not ready:
        print(
            "Skipping Vercel deploy: set repository secrets "
            "VERCEL_TOKEN, VERCEL_ORG_ID, and VERCEL_PROJECT_ID.",
            file=sys.stderr,
        )
    return 0


def _cmd_pull() -> int:
    run_vercel(pull_argv(resolve_environment_from_env()))
    return 0


def _cmd_build() -> int:
    run_vercel(build_argv(resolve_environment_from_env()))
    return 0


def _cmd_deploy() -> int:
    url = run_vercel(
        deploy_argv(resolve_environment_from_env()),
        capture_stdout=True,
    )
    write_github_output({"url": url})
    if url:
        print(url)
    return 0


def _cmd_comment(url: str, sha: str) -> int:
    sys.stdout.write(preview_comment_body(url=url, sha=sha))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("gate", help="Write can_deploy + environment to GITHUB_OUTPUT")
    sub.add_parser("install-spec", help="Print the pinned vercel@X.Y.Z spec")
    sub.add_parser("environment", help="Print preview or production")
    sub.add_parser("pull", help="vercel pull --yes (token from env)")
    sub.add_parser("build", help="vercel build [--prod]")
    sub.add_parser("deploy", help="vercel deploy --prebuilt [--prod]")
    comment = sub.add_parser("comment", help="Print the PR preview comment body")
    comment.add_argument("--url", required=True)
    comment.add_argument("--sha", default=os.environ.get("GITHUB_SHA", ""))
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "install-spec":
        print(install_cli_spec())
        return 0
    if args.command == "environment":
        print(resolve_environment_from_env())
        return 0
    dispatch = {
        "gate": _cmd_gate,
        "pull": _cmd_pull,
        "build": _cmd_build,
        "deploy": _cmd_deploy,
    }
    if args.command in dispatch:
        return dispatch[args.command]()
    return _cmd_comment(args.url, args.sha)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Emit a Buildkite pipeline for hermes-agent.

The GitHub Actions orchestrator (``.github/workflows/ci.yaml``) is still the
merge gate. This pipeline is the Buildkite equivalent of the Linux lanes:
cheap always-on guards, then the ``classify_changes.py``-gated ruff / pytest /
``uv lock --check`` / JS checks.

Usage:
    python3 scripts/ci/buildkite_pipeline.py              # classify HEAD, dump YAML
    python3 scripts/ci/buildkite_pipeline.py --fail-open  # every Linux lane
    python3 scripts/ci/buildkite_pipeline.py | buildkite-agent pipeline upload

Paste the YAML into Buildkite's Steps editor when the "couldn't scan this
repository" picker fails (the GitHub App cannot list files). The commands
only call scripts that already exist on main, plus installing uv/node.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

_CLASSIFY_PATH = Path(__file__).resolve().parent / "classify_changes.py"

# Keep in sync with .github/workflows/tests.yml / lint.yml.
UV_VERSION = "0.9.28"
PYTHON_VERSION = "3.11"
NODE_MAJOR = "26"
RG_VERSION = "15.1.0"
RG_SHA256 = "1c9297be4a084eea7ecaedf93eb03d058d6faae29bbc57ecdaf5063921491599"

# Same extras list as the GitHub pytest lane. The hermetic runner forbids
# mid-run pip installs, so lazy-install SDKs must be in the venv up front.
UV_SYNC = (
    f"uv sync --locked --python {PYTHON_VERSION} --extra all --extra dev "
    "--extra anthropic --extra mistral --extra fal --extra modal "
    "--extra daytona --extra hindsight --extra parallel-web"
)

_AGENT_RETRY = {
    "automatic": [
        {"exit_status": -1, "limit": 2},
    ]
}


def _classify_mod() -> Any:
    spec = importlib.util.spec_from_file_location("classify_changes", _CLASSIFY_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load {_CLASSIFY_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pipeline_env() -> dict[str, str]:
    """Job env. Credential vars blanked so a leaked agent env cannot call APIs."""
    return {
        "OPENROUTER_API_KEY": "",
        "OPENAI_API_KEY": "",
        "NOUS_API_KEY": "",
        "UV_VERSION": UV_VERSION,
        "PYTHON_VERSION": PYTHON_VERSION,
    }


def _uv_prelude() -> str:
    # ``$$`` survives Buildkite interpolation and becomes ``$`` in the shell.
    return f"""set -euo pipefail
curl -LsSf "https://astral.sh/uv/{UV_VERSION}/install.sh" | sh
export PATH="$$HOME/.local/bin:$$PATH"
"""


def _node_prelude() -> str:
    """Install Node from nodejs.org. nvm's install.sh exits 3 in CI.

    The installer prints "Close and reopen your terminal" and then returns 3
    in a non-interactive shell (no profile to edit, nvm not loaded). With
    ``set -euo pipefail``, ``curl | bash`` aborts the job before ``. nvm.sh``.
    """
    # ``$$`` / ``{{`` survive Buildkite interpolation and f-string braces.
    return f"""if ! command -v node >/dev/null 2>&1 || ! node -v | grep -q '^v{NODE_MAJOR}\\.'; then
  NODE_ARCH=$$(uname -m)
  case "$$NODE_ARCH" in
    x86_64) NODE_ARCH=x64 ;;
    aarch64|arm64) NODE_ARCH=arm64 ;;
    *) echo "unsupported arch: $$NODE_ARCH" >&2; exit 1 ;;
  esac
  NODE_TMP=$$(mktemp -d)
  curl -fsSL --retry 3 --retry-delay 5 \\
    "https://nodejs.org/dist/latest-v{NODE_MAJOR}.x/SHASUMS256.txt" \\
    -o "$$NODE_TMP/SHASUMS256.txt"
  NODE_TARBALL=""
  NODE_HASH=""
  while read -r NODE_HASH NODE_TARBALL; do
    case "$$NODE_TARBALL" in
      node-v*-linux-"$$NODE_ARCH".tar.gz)
        break
        ;;
    esac
    NODE_TARBALL=""
    NODE_HASH=""
  done < "$$NODE_TMP/SHASUMS256.txt"
  if [ -z "$$NODE_TARBALL" ] || [ -z "$$NODE_HASH" ]; then
    echo "could not resolve node {NODE_MAJOR} linux-$$NODE_ARCH tarball" >&2
    cat "$$NODE_TMP/SHASUMS256.txt" >&2
    exit 1
  fi
  curl -fsSL --retry 3 --retry-delay 5 \\
    "https://nodejs.org/dist/latest-v{NODE_MAJOR}.x/$$NODE_TARBALL" \\
    -o "$$NODE_TMP/$$NODE_TARBALL"
  echo "$$NODE_HASH  $$NODE_TMP/$$NODE_TARBALL" | sha256sum -c -
  rm -rf "$$HOME/.local/node"
  mkdir -p "$$HOME/.local/node"
  tar -xzf "$$NODE_TMP/$$NODE_TARBALL" -C "$$HOME/.local/node" --strip-components=1
  rm -rf "$$NODE_TMP"
fi
export PATH="$$HOME/.local/node/bin:$$PATH"
node --version
npm --version
"""


def _rg_prelude() -> str:
    return f"""if ! command -v rg >/dev/null 2>&1; then
  RG_TARBALL="ripgrep-{RG_VERSION}-x86_64-unknown-linux-musl.tar.gz"
  curl -sSfL --retry 3 --retry-delay 5 -o "$$RG_TARBALL" \\
    "https://github.com/BurntSushi/ripgrep/releases/download/{RG_VERSION}/$$RG_TARBALL"
  echo "{RG_SHA256}  $$RG_TARBALL" | sha256sum -c -
  tar -xzf "$$RG_TARBALL"
  if command -v sudo >/dev/null 2>&1; then
    sudo mv "ripgrep-{RG_VERSION}-x86_64-unknown-linux-musl/rg" /usr/local/bin/rg
  else
    mkdir -p "$$HOME/.local/bin"
    mv "ripgrep-{RG_VERSION}-x86_64-unknown-linux-musl/rg" "$$HOME/.local/bin/rg"
    export PATH="$$HOME/.local/bin:$$PATH"
  fi
  rm -rf "$$RG_TARBALL" "ripgrep-{RG_VERSION}-x86_64-unknown-linux-musl"
fi
rg --version
"""


def _step(
    label: str,
    command: str,
    *,
    key: str,
    timeout: int,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    step: dict[str, Any] = {
        "label": label,
        "key": key,
        "command": command,
        "timeout_in_minutes": timeout,
        "retry": _AGENT_RETRY,
    }
    if env:
        step["env"] = env
    return step


def always_on_steps() -> list[dict[str, Any]]:
    """Guards that GitHub runs unconditionally (not language-gated)."""
    infographic = """set -euo pipefail
OFFENDERS=$(git ls-files -z | tr '\\0' '\\n' | grep -iE '(^|/)(infograph|infograf)[^/]*/' | grep -iE '\\.(png|jpe?g|webp|gif)$' || true)
if [ -n "$$OFFENDERS" ]; then
  echo "PR-infographic image(s) are tracked in git:"
  printf '%s\\n' "$$OFFENDERS"
  echo "Infographic images belong in the PR description, never in git."
  exit 1
fi
echo "No committed PR-infographic images."
"""
    return [
        _step(
            ":file_folder: Case collisions",
            "set -euo pipefail\npython3 scripts/check-case-collisions.py\n",
            key="case-collisions",
            timeout=5,
        ),
        _step(
            ":frame_with_picture: Infographic check",
            infographic,
            key="infographic",
            timeout=10,
        ),
        _step(
            ":package: Profile artifact check",
            "set -euo pipefail\npython3 scripts/ci/check_profile_archive_boundary.py\n",
            key="profile-artifacts",
            timeout=5,
        ),
    ]


def python_steps() -> list[dict[str, Any]]:
    ruff = _uv_prelude() + "uv tool install ruff\nruff check .\n"
    footguns = (
        _uv_prelude()
        + f"uv python install {PYTHON_VERSION}\n"
        + f"uv run --python {PYTHON_VERSION} --no-project "
        + "python scripts/check-windows-footguns.py --all\n"
        + f"uv run --python {PYTHON_VERSION} --no-project "
        + "python scripts/check_compat_pointers.py\n"
    )
    tests = (
        _uv_prelude()
        + _rg_prelude()
        + f"uv python install {PYTHON_VERSION}\n"
        + UV_SYNC
        + "\n"
        + "source .venv/bin/activate\n"
        + "scripts/run_tests.sh\n"
    )
    return [
        _step(":ruff: ruff check", ruff, key="ruff", timeout=5),
        _step(
            ":warning: Windows footguns + compat pointers",
            footguns,
            key="footguns",
            timeout=5,
        ),
        _step(
            ":pytest: Linux tests",
            tests,
            key="pytest",
            timeout=60,
            env={
                "OPENROUTER_API_KEY": "",
                "OPENAI_API_KEY": "",
                "NOUS_API_KEY": "",
            },
        ),
    ]


def uv_lock_steps() -> list[dict[str, Any]]:
    command = (
        _uv_prelude()
        + f"uv python install {PYTHON_VERSION}\n"
        + f"uv lock --check --python {PYTHON_VERSION}\n"
    )
    return [
        _step(":lock: uv.lock check", command, key="uv-lock", timeout=5),
    ]


def frontend_steps() -> list[dict[str, Any]]:
    command = (
        "set -euo pipefail\n"
        + _node_prelude()
        + "npm --version | grep -q '^12\\.' || npm i -g npm@12\n"
        + "npm ci\n"
        + "node .github/scripts/run-workspace-checks.mjs\n"
    )
    return [
        _step(":node: JS & TS checks", command, key="js-checks", timeout=30),
    ]


def emit_steps(lanes: dict[str, bool]) -> list[dict[str, Any]]:
    """Build the Buildkite ``steps:`` list for the given classifier lanes."""
    steps: list[dict[str, Any]] = [
        {
            "group": ":zap: Always-on guards",
            "key": "guards",
            "steps": always_on_steps(),
        }
    ]
    if lanes.get("python"):
        steps.append(
            {
                "group": ":python: Python",
                "key": "python",
                "steps": python_steps(),
            }
        )
    if lanes.get("uv_lock"):
        steps.append(
            {
                "group": ":lock: Lockfile",
                "key": "lockfile",
                "steps": uv_lock_steps(),
            }
        )
    if lanes.get("frontend"):
        steps.append(
            {
                "group": ":node: Frontend",
                "key": "frontend",
                "steps": frontend_steps(),
            }
        )
    return steps


def collect_commands(steps: list[dict[str, Any]]) -> list[str]:
    """Flatten ``command`` strings out of (possibly grouped) steps."""
    found: list[str] = []
    for step in steps:
        if "command" in step:
            found.append(str(step["command"]))
        nested = step.get("steps")
        if isinstance(nested, list):
            found.extend(collect_commands(nested))
    return found


def changed_files() -> list[str]:
    """PR paths vs the base branch, or ``[]`` (fail-open) on branch builds."""
    pr = os.environ.get("BUILDKITE_PULL_REQUEST", "false")
    if pr in ("", "false", "False"):
        return []
    base = os.environ.get("BUILDKITE_PULL_REQUEST_BASE_BRANCH") or "main"
    subprocess.run(
        ["git", "fetch", "--no-tags", "--depth=200", "origin", base],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    diff = subprocess.run(
        ["git", "diff", "--name-only", f"origin/{base}...HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if diff.returncode != 0:
        return []
    return [line.strip() for line in diff.stdout.splitlines() if line.strip()]


def render_yaml(data: dict[str, Any]) -> str:
    class _Dumper(yaml.SafeDumper):
        pass

    def _str_presenter(dumper: yaml.SafeDumper, value: str) -> Any:
        if "\n" in value:
            return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", value)

    _Dumper.add_representer(str, _str_presenter)
    dumped = yaml.dump(
        data,
        Dumper=_Dumper,
        sort_keys=False,
        default_flow_style=False,
        width=120,
        allow_unicode=True,
    )
    if not dumped.endswith("\n"):
        dumped += "\n"
    return dumped


_HEADER = """# Hermes Agent — Buildkite pipeline
#
# Paste this file into the pipeline's YAML Steps editor (the Hello world
# template). Use YAML steps, not "Steps from repository", until the Buildkite
# GitHub App can list files — that picker is what shows
# "Buildkite couldn't scan this repository".
#
# After the App is installed on this GitHub org with Contents: Read, switch
# the pipeline to "Use steps from repository" → `.buildkite/pipeline.yml`.
#
# Agents: Linux with curl, python3, and enough CPU/RAM for pytest. GitHub's
# pytest lane uses 96 cores; here `scripts/run_tests.sh` sizes workers from
# nproc. To pin a queue, add under a step:
#   agents:
#     queue: "linux-large"
#
# This file is the fail-open (every Linux lane) dump. On Buildkite, prefer
#   python3 scripts/ci/buildkite_pipeline.py | buildkite-agent pipeline upload
# so PRs skip lanes the change classifier would skip.

"""


def build_pipeline(lanes: dict[str, bool]) -> dict[str, Any]:
    return {"env": pipeline_env(), "steps": emit_steps(lanes)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fail-open",
        action="store_true",
        help="Emit every Linux lane (empty diff / push-to-main behaviour).",
    )
    args = parser.parse_args(argv)
    classify = _classify_mod().classify
    files = [] if args.fail_open else changed_files()
    lanes = classify(files)
    sys.stdout.write(_HEADER)
    sys.stdout.write(render_yaml(build_pipeline(lanes)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

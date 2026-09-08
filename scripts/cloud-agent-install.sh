#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for hermes-agent.
#
# The personal Cursor environment's `install` command points at this path.
# Recurring environment builds fail with exit 127 when the file is missing.
#
# Creates `.venv` from uv.lock with the same extras as
# `.github/workflows/tests.yml` so `scripts/run_tests.sh` can run under
# HERMES_DISABLE_LAZY_INSTALLS=1 without mid-run pip. Non-interactive;
# does not start servers.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PATH="${HOME}/.local/bin:${PATH}"

if ! command -v uv >/dev/null 2>&1; then
  echo "→ installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# `uv sync --locked` creates `.venv` itself. Prefer the already-provisioned
# 3.11 interpreter (CI's version) so we do not pull 3.14 via UV_PYTHON.
echo "→ uv sync --locked (all, dev, and test-required lazy extras)"
uv sync --locked --python 3.11 \
  --extra all --extra dev \
  --extra anthropic --extra mistral --extra fal \
  --extra modal --extra daytona --extra hindsight --extra parallel-web

.venv/bin/python -c 'import hermes_cli, pytest; print("cloud-agent-install: ok")'

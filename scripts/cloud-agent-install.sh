#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for hermes-agent.
#
# Prepares the full development experience against Cursor's default base image:
#   * uv + a Python 3.11 virtualenv at ./.venv from uv.lock (`uv sync --frozen`)
#     with the same extras as `.github/workflows/tests.yml` so
#     `scripts/run_tests.sh` can run under HERMES_DISABLE_LAZY_INSTALLS=1
#     without mid-run pip.
#   * Node.js pinned by .nvmrc (>= the root package.json `engines` floor), so
#     the JS workspaces (dashboard, TUI) and browser tools resolve.
#   * The `web` dashboard workspace, built into hermes_cli/web_dist so
#     `hermes dashboard` serves a real UI out of the box.
#   * Interactive shells auto-activate the venv so `hermes`, `python`, `pytest`,
#     `ruff`, and `ty` resolve to the project interpreter.
#
# The personal Cursor environment's `install` command points at this path.
# Recurring environment builds fail with exit 127 when the file is missing.
# Non-interactive; does not start servers.
# Safe to run repeatedly: every step is a no-op refresh when already satisfied.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PATH="$HOME/.local/bin:$PATH"

echo "▶ [1/5] Ensuring uv is installed"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv --version

echo "▶ [2/5] Creating Python 3.11 venv from uv.lock (all, dev, and test extras)"
# `uv sync --frozen` installs uv.lock as-is without rewriting it. `--locked`
# fails here when pyproject exclude-newer exceptions (e.g. `h2`) have expired
# relative to the lockfile; environment bootstrap must not run `uv lock`.
# Prefer the already-provisioned 3.11 interpreter (CI's version / .python-version)
# so we do not pull 3.14 via UV_PYTHON.
PYTHON_VERSION="$(cat .python-version 2>/dev/null || echo 3.11)"
uv sync --frozen --python "$PYTHON_VERSION" \
  --extra all --extra dev \
  --extra anthropic --extra mistral --extra fal \
  --extra modal --extra daytona --extra hindsight --extra parallel-web
# shellcheck disable=SC1091
source .venv/bin/activate
.venv/bin/python -c 'import hermes_cli, pytest; print("cloud-agent-install: ok")'

echo "▶ [3/5] Installing Node.js $(cat .nvmrc 2>/dev/null || echo 26) via nvm"
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
fi
# shellcheck disable=SC1091
. "$NVM_DIR/nvm.sh"
NODE_VERSION="$(cat .nvmrc 2>/dev/null || echo 26)"
nvm install "$NODE_VERSION"
nvm alias default "$NODE_VERSION"
# The base image ships a shadowing node on PATH ahead of nvm; publish the
# pinned node/npm/npx into ~/.local/bin (earlier on PATH) so the project uses it.
NODE_BIN_DIR="$(dirname "$(nvm which "$NODE_VERSION")")"
mkdir -p "$HOME/.local/bin"
for b in node npm npx; do ln -sf "$NODE_BIN_DIR/$b" "$HOME/.local/bin/$b"; done
hash -r
echo "  node $(node --version) / npm $(npm --version)"

echo "▶ [4/5] Installing + building the web dashboard workspace"
# --no-save keeps the committed root lockfile untouched (a single-workspace
# install otherwise rewrites esbuild peer metadata).
npm install --workspace web --no-save
npm run --workspace web build

echo "▶ [5/5] Wiring interactive shells to the project venv"
GUARD="# >>> hermes-agent venv >>>"
if ! grep -qF "$GUARD" "$HOME/.bashrc" 2>/dev/null; then
  {
    echo ""
    echo "$GUARD"
    echo "[ -f \"$REPO_ROOT/.venv/bin/activate\" ] && source \"$REPO_ROOT/.venv/bin/activate\""
    echo "# <<< hermes-agent venv <<<"
  } >> "$HOME/.bashrc"
fi

echo "✅ hermes-agent environment ready."

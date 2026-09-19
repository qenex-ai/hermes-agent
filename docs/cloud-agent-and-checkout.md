# Cloud agents and checkout paths

## Checkout locations

The Hermes tree may appear as:

| Path | Typical use |
| --- | --- |
| `/workspace` | Cursor Cloud Agent default mount |
| `/root/hermes-src` | Deploy / internal mirror (symlink or clone of the same repo) |

Agent instructions live in **`AGENTS.md` at the repo root** (whichever path is mounted).
If `/root/hermes-src` is missing, create a symlink: `ln -sfn /workspace /root/hermes-src`.

## Bootstrap

One-shot install (matches CI test extras + dashboard bundle):

```bash
scripts/cloud-agent-install.sh
source .venv/bin/activate
```

Do not add long-running servers to that script; use the environment **start** command or a
dedicated terminal session instead.

## Optional: dashboard for manual UI checks

After `cloud-agent-install.sh` (or `npm run build --workspace web`):

```bash
source .venv/bin/activate
hermes dashboard
```

Bind/host/port follow your local `config.yaml` and CLI defaults. Leave the process running
in tmux if you need it across agent turns.

## Agent context files

- **Every session:** root `AGENTS.md` + area `AGENTS.md` from the routing table.
- **On demand:** `website/docs/developer-guide/agents-reference-extended.md` (full rubric and testing reference).

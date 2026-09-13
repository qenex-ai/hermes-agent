---
name: qenex-ops
description: "Classify Lab leads and draft replies; never send or spend."
version: 1.0.0
author: Abdulrahman Almutairi (abdulrahman305), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [QENEX, Lab, Ops, Cron, Productivity]
    category: productivity
    related_skills: [email-inbox-triage]
    config:
      - key: qenex_ops.contact_email
        description: Public contact quoted in license drafts
        default: ceo@qenex.ai
        prompt: Contact email for Lab license drafts
---

# QENEX Ops Skill

Installs a zero-token Lab ops loop for QENEX LTD: classify inbound items, draft license replies, and queue money/legal work for a human. It does not make the company legally autonomous, maximize profit, or eliminate hosting or Lab compute cost. Pulse stays archived; outbound mail and spend are refused in code.

## When to Use

- "Set up QENEX LTD to run autonomously."
- "Install the QENEX ops loop / zero-cost cron tick."
- "Triage Lab license leads and verifier clones."
- A `cronjob` tick fires for `qenex-ops-tick` (`no_agent=True`).

Don't use for: paying invoices, filing Companies House, signing licenses, sending mail, buying ads, or reviving Pulse.

## Prerequisites

- Hermes home writable (`HERMES_HOME` / `get_hermes_home()`). Profiles stay isolated.
- Optional: drop inbound JSON into `$HERMES_HOME/qenex-ops/inbox/` (see `templates/inbox-item.json`). Connector skills (`email-inbox-triage`) own mailbox fetch; this skill owns classify + draft.
- Gateway running if you want cron delivery later. Setup defaults `deliver=local` (disk only).

## How to Run

Setup (foreground, once) via `terminal`:

```
hermes qenex setup
```

That copies the script into `$HERMES_HOME/scripts/qenex_ops.py` (the only path cron will execute), copies this skill into `$HERMES_HOME/skills/qenex-ops/`, and creates a `no_agent` cron job. The builtin ticker lives in the gateway — start it with `hermes gateway install` or the jobs never fire. Empty ticks print nothing (`[SILENT]`).

Tick (each scheduled run) is the cron script itself. Do not schedule an agent job for this loop — that burns tokens. Foreground tick:

```
hermes qenex tick
```

Drop raw mail into `$HERMES_HOME/qenex-ops/mailbox/*.eml` (the tick turns them into inbox JSON) or enqueue a test lead, then `status`:

```
hermes qenex enqueue --from "pi@example.ac.uk" --subject "Lab license" --body "We want a quantum chemistry academic license for our group."
hermes qenex tick
hermes qenex status
```

## Quick Reference

| Command | What it does |
|---|---|
| `hermes qenex setup` / `init` | State dirs, skill copy, `no_agent` cron job |
| `hermes qenex tick` | Ingest `.eml`, classify inbox; silent if empty |
| `hermes qenex enqueue` / `add` | Drop one JSON item into the inbox |
| `hermes qenex status` / `st` | Queue counts + last tick |

Invariants (not config): `auto_send=false`, `spend_allowed=false`, product=`lab`.

## Procedure — Setup (foreground, once)

### 1. Freeze the product and gates

QENEX LTD sells QENEX Lab only. Pulse is archived. Director duties, payments, patents, and send stay human (`references/human-gates.md`). Done when the ledger at `$HERMES_HOME/qenex-ops/ledger.json` shows `product=lab`, `auto_send=false`, `spend_allowed=false`.

### 2. Install state and the cron script

Run `hermes qenex setup` via `terminal`. Confirm `$HERMES_HOME/scripts/qenex_ops.py` exists (cron refuses paths outside `scripts/`). Done when `setup-receipt.json` lists `cron.no_agent=true` (or `--no-cron` was explicit).

### 3. Prove one foreground tick

`enqueue` a Lab-license item, run `tick`, `read_file` the draft under `$HERMES_HOME/qenex-ops/drafts/`. The draft must contain `send: false`. Do not schedule until one foreground fetch works. Then leave the `no_agent` job running:

```
cronjob(action="create",
        schedule="every 30m",
        script="qenex_ops.py",
        no_agent=true,
        deliver="local")
```

Skip this `cronjob` call if setup already created `qenex-ops-tick`. Done when `hermes cron list` (or `cronjob(action="list")`) shows that job.

## Procedure — Tick (each scheduled run)

### 4. Collect the inbox

Read `$HERMES_HOME/qenex-ops/inbox/*.json` after ingesting `$HERMES_HOME/qenex-ops/mailbox/*.eml`. Items already in `seen.json` move to `processed/` without re-drafting. Connector fetch is out of scope for the tick (keep the tick zero-token). Done when every file is classified or skipped as seen.

### 5. Classify with the profit ranking

`lab_license` (highest) then `verifier_signal`, `pulse_archive` (redirect, do not revive), `human_gate` (approvals queue), `spend_refuse` (refused/), `noise`. A customer asking to buy a Lab license is revenue, not spend. "Buy ads" / "hire" / "purchase GPU" is spend and is refused. Done when each item has one kind and `send=false` / `spend=false`.

### 6. Draft or hold; never send

Write drafts for Lab/verifier/Pulse-redirect. Human-gate items go to `approvals/` with no outbound. Spend attempts go to `refused/` with a reason. If nothing actionable, print nothing. Done when `last-tick.json` matches the queues and no draft has `send=true`.

## Pitfalls

- Treating "fully autonomous / zero cost / max profit" as a real target. This loop is the honest subset.
- Creating an agent `cronjob` instead of `no_agent=true` — that is not zero-cost.
- Sending a draft, flipping `auto_send` in the ledger (the script overwrites it), or paying from Pulse-era playbooks.
- Putting the tick script outside `$HERMES_HOME/scripts/` — the scheduler blocks it.
- Using `email-inbox-triage` send/delete as if this skill authorized it. It does not.

## Verification

- [ ] `setup` wrote `$HERMES_HOME/qenex-ops/setup-receipt.json` with `no_agent` true (unless `--no-cron`).
- [ ] A Lab-license inbox item produced a draft whose `ops.send` is false.
- [ ] A "buy ads" item landed in `refused/` and did not create a sendable draft.
- [ ] Empty tick stdout is empty (cron silent path).
- [ ] `ledger.json` still has `auto_send=false` after a tick even if it was edited to true.

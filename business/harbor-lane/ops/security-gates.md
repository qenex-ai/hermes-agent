# Security gates — Harbor Lane go-live

Verified 2026-09-13 via `aide_gate_status`: kill switch **off**, pending gates **0**.

## Gate checks before infra writes

| Action | Tool | Gate |
|---|---|---|
| DNS record write | `qenex_dns_zone_edit` | SSO + `confirm=true` after dry-run |
| Mail server provision | `qenex_mail_host` | SSO + aide gate if tier=hard_gate |
| Domain register | `qenex_domain_registrar` | **BLOCKED** for .co.uk/.com (external track) |
| Site deploy | `qenex_site_provisioner` | SSO required |

## Attempted dry-runs (this deployment)

| Tool | Result |
|---|---|
| `aide_gate_status` | OK — no pending gates |
| `qenex_dns_zone_edit` (dry_run=true) | Blocked — Keycloak SSO required |
| `qenex_mail_host` preflight | Blocked — Keycloak SSO required |
| `qenex_site_provisioner` list_sites | Blocked — Keycloak SSO required |

**Operator action:** Founder with SSO session must execute DNS, mail, and site provision steps in `go-live-checklist.md`.

## What was completed without gates

- Supabase schema + RLS + seed data (via Supabase MCP)
- Application code (web + mobile)
- CI workflow
- Legal pages and ops documentation

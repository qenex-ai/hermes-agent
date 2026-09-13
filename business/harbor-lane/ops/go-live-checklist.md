# Harbor Lane Advisory — Go-live checklist

Hostname: **https://harborlane.qenex.dev**

## Pre-flight (security gates)

- [ ] `aide_gate_status` — kill switch off, no blocking pending gates
- [ ] Founder confirms: no `.co.uk`/`.com` registration via QENEX
- [ ] Founder confirms: CH/VAT/ICO on external track only

## DNS & TLS

- [ ] `qenex_dns_zone_edit` dry-run for `harborlane.qenex.dev` A/CNAME record
- [ ] Human approves gate → apply DNS with `dry_run=false`, `confirm=true`
- [ ] `qenex_site_provisioner` create_site for `harborlane.qenex.dev`
- [ ] Verify TLS: `curl -I https://harborlane.qenex.dev`
- [ ] Optional: `portal.harborlane.qenex.dev` CNAME if split later

## Mail (IMAP day-one)

- [ ] `qenex_mail_host` action=preflight domain=harborlane.qenex.dev
- [ ] Gate approval → action=provision_mailserver
- [ ] Create mailboxes: hello, support, admin, billing, noreply
- [ ] Store credentials in founder password manager (shown once)
- [ ] Add MX/SPF/DKIM DNS records from preflight output
- [ ] Test: send to support@, read via IMAP mail.qenex.ai:993

## Backend (Supabase)

- [x] Schema + RLS applied (migration `harbor_lane_initial_schema`)
- [x] Seed: firm, 3 customers, 2 leads, 1 project, 1 invoice, chart of accounts
- [ ] Create staff auth user + profiles row (role: owner)
- [ ] Create client auth user + profiles row (role: client, customer_id set)
- [ ] Verify RLS: staff sees all customers; client sees own data only

## Web deploy

- [ ] Set env: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- [ ] `npm run build` in `web/`
- [ ] Deploy build to `/var/www/harborlane.qenex.dev/` or Vercel
- [ ] Smoke: `/`, `/portal`, `/admin`, `/privacy`, `/support`

## Billing day-one

- [ ] Staff can list invoices at `/admin/invoices`
- [ ] Create draft invoice at `/admin/invoices/new`
- [ ] Mark sent → email PDF to client from billing@
- [ ] Xero: connect external account, map chart_of_accounts codes

## Mobile

- [ ] `expo build` or EAS for iOS/Android
- [ ] Set `EXPO_PUBLIC_SUPABASE_*` env
- [ ] Test projects, invoices, messages screens with client login

## Legal pages (live)

- [x] `/privacy` — UK GDPR, ICO external track noted
- [x] `/terms` — England & Wales governing law
- [x] `/cookies`
- [x] `/support` — hello@, support@, billing@

## CI

- [ ] `.github/workflows/harbor-lane-ci.yml` green on PR

## Day-one acceptance

Founder can:
1. **Take a client** — view/create customer in admin CRM
2. **Send an invoice** — draft + send HL-2026-00x from billing@
3. **Answer support@** — IMAP configured, mailbox reachable

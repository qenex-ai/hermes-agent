# Harbor Lane Advisory — Agent Guide

London professional-services firm (retainers + project work for UK SMEs). Day-one hostname: **harborlane.qenex.dev**.

## Boundaries (do not cross)

| Track | Rule |
|---|---|
| **qenex.dev hostname** | Ship web, portal, admin here via QENEX site provisioner |
| **.co.uk / .com names** | External track only — **never** register via `qenex_domain_registrar` |
| **Companies House, VAT, ICO** | Founder's external track — **never** file via QENEX (`qenex_ch_filing_*`, `qenex_hmrc_*`) |

## Stack

| Surface | Path | Backend |
|---|---|---|
| Marketing + legal | `web/src/app/` | Static/SSR Next.js 15 |
| Client portal | `web/src/app/portal/` | Supabase RLS (client role) |
| Staff admin | `web/src/app/admin/` | Supabase RLS (staff roles) |
| Mobile | `mobile/app/` | Expo + Supabase |
| Database | Supabase project `qenex` (eu-west-2) | `customers`, `leads`, `projects`, `invoices`, `messages`, `chart_of_accounts` |

## Security gates (required before infra writes)

1. **`aide_gate_status`** — no kill switch; approve pending gates before DNS/mail/register
2. **DNS** — `qenex_dns_zone_edit` with `dry_run=true` first; `confirm=true` only after human approval
3. **Mail** — `qenex_mail_host` preflight → provision → create mailboxes (credentials returned once)
4. **Domain register** — **never** for `.co.uk`/`.com`; qenex.dev subdomains use DNS only

## Mailboxes (day-one)

| Address | Purpose |
|---|---|
| hello@harborlane.qenex.dev | General enquiries |
| support@harborlane.qenex.dev | Client support (answer same day) |
| admin@harborlane.qenex.dev | Internal ops |
| billing@harborlane.qenex.dev | Invoices and payment queries |
| noreply@harborlane.qenex.dev | System notifications |

IMAP: `mail.qenex.ai:993` TLS · SMTP: `mail.qenex.ai:587` STARTTLS

## Dev commands

```bash
cd business/harbor-lane/web && npm install && npm run dev   # :3100
cd business/harbor-lane/mobile && npm install && npm start
```

## Auth provisioning

1. Create Supabase Auth users (Dashboard → Authentication)
2. Insert matching `profiles` row with `firm_id`, `role` (`owner`|`admin`|`consultant`|`client`), and `customer_id` for clients
3. RLS enforces access — no service-role in browser

## Xero sync

Chart of accounts seeded with UK SME codes (200 Sales, 201 Retainer, 820 VAT, etc.). Map `xero_account_id` on first Xero connection — use founder's external Xero account, not QENEX filing tools.

# Mail plan — harborlane.qenex.dev

## Required mailboxes

| Mailbox | Role |
|---|---|
| hello@harborlane.qenex.dev | Inbound sales / general |
| support@harborlane.qenex.dev | Client support (day-one answer target) |
| admin@harborlane.qenex.dev | Internal / DMARC reports |
| billing@harborlane.qenex.dev | Invoice send + payment queries |
| noreply@harborlane.qenex.dev | Portal/system notifications |

## Provisioning sequence

1. **Preflight** (read-only): `qenex_mail_host` action=preflight domain=harborlane.qenex.dev
2. **Gate check**: `aide_gate_status` — approve if required
3. **Provision server**: action=provision_mailserver (Postfix + Dovecot + DKIM)
4. **Create mailboxes**: action=create_mailbox for each user above
5. **IMAP test**: connect mail.qenex.ai:993 TLS with generated credentials

## Client IMAP/SMTP settings (for founder)

| Setting | Value |
|---|---|
| IMAP host | mail.qenex.ai |
| IMAP port | 993 (SSL/TLS) |
| SMTP host | mail.qenex.ai |
| SMTP port | 587 (STARTTLS) |
| Username | full mailbox address |

## Outbound invoice flow

1. Staff creates invoice in `/admin/invoices/new`
2. Export PDF (manual or future automation)
3. Send from billing@ via IMAP client or `qenex_mail_draft` + human-approved send
4. Update invoice status to `sent` in admin

**Never** auto-send mail without explicit founder approval per QENEX ops gates.

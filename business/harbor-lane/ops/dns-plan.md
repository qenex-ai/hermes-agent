# DNS plan — harborlane.qenex.dev

## Hostname strategy

| Host | Purpose | Record type |
|---|---|---|
| harborlane.qenex.dev | Marketing + portal + admin (Next.js) | A or CNAME → QENEX edge |
| mail.harborlane.qenex.dev | Optional mail subdomain | CNAME → mail.qenex.ai |

**Note:** QENEX authoritative zones currently include `db.qenex.ai`. The `qenex.dev` zone may live on external registrar — coordinate with ops. Do **not** register harborlane.co.uk via QENEX.

## Proposed records (dry-run before apply)

```
harborlane.qenex.dev.  300  IN  A      198.244.164.221
harborlane.qenex.dev.  300  IN  TXT    "v=spf1 mx a:mail.qenex.ai ~all"
_dmarc.harborlane.qenex.dev. 300 IN TXT "v=DMARC1; p=quarantine; rua=mailto:admin@harborlane.qenex.dev"
```

## Security gate workflow

```bash
# 1. Dry run only
qenex_dns_zone_edit(zone_file=db.qenex.ai, operation=add, record_name=harborlane, ..., dry_run=true)

# 2. Check aide_gate_status — approve if gated

# 3. Apply with confirm
qenex_dns_zone_edit(..., dry_run=false, confirm=true)
```

## TLS

Handled by Caddy via `qenex_site_provisioner` action=create_site. Renew with action=renew_tls.

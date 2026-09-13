# Harbor Lane Advisory Ltd

**Day-one UK operating business** — London professional services firm selling retainers and project work to UK SMEs.

- **Live hostname:** https://harborlane.qenex.dev
- **Backend:** Supabase (`qenex` project, eu-west-2) with RLS
- **Not a demo:** seeded customers, leads, project, and invoice HL-2026-001

## Surfaces

| Surface | URL / path |
|---|---|
| Marketing | `/` |
| Client portal | `/portal` |
| Staff admin | `/admin` |
| Legal | `/privacy`, `/terms`, `/cookies`, `/support` |
| Mobile | `mobile/` — Expo iOS + Android |

## Quick start

```bash
cd web
cp .env.example .env.local
# Add NEXT_PUBLIC_SUPABASE_ANON_KEY from Supabase dashboard
npm install
npm run dev
```

Open http://localhost:3100

## External track (founder only)

- `.co.uk` / `.com` domain registration
- Companies House filings
- VAT registration and HMRC
- ICO registration

These are **never** done via QENEX automation. See `AGENTS.md` and `ops/go-live-checklist.md`.

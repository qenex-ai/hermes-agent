# Supabase migrations

Applied to project `qenex` (ref: `ndcbxdhskpcamuunmkmk`, region: eu-west-2):

| Version | Name | Status |
|---|---|---|
| 20260913155326 | harbor_lane_initial_schema | Applied |

Schema includes: `firms`, `profiles`, `customers`, `leads`, `projects`, `invoices`, `invoice_line_items`, `messages`, `chart_of_accounts` with RLS policies.

Re-apply to a fresh project via Supabase MCP `apply_migration` or Dashboard SQL editor.

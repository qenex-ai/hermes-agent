import { createClient } from "@/lib/supabase/server";
import { formatDate, formatGbp, statusBadgeClass } from "@/lib/format";
import type { Invoice } from "@/lib/types";

export default async function PortalInvoicesPage() {
  const supabase = await createClient();
  const { data, error } = await supabase.from("invoices").select("*").order("issue_date", { ascending: false });
  const invoices = (data ?? []) as Invoice[];

  return (
    <div>
      <h1 className="text-2xl font-bold text-harbor-900">Your invoices</h1>
      <p className="mt-2 text-sm text-gray-600">
        Questions? Email{" "}
        <a href="mailto:billing@harborlane.qenex.dev" className="text-harbor-700 underline">
          billing@harborlane.qenex.dev
        </a>
      </p>
      {error && (
        <p className="mt-4 rounded-lg bg-amber-50 p-4 text-sm text-amber-800">
          Sign in with your client account to view invoices.
        </p>
      )}
      <div className="mt-6 space-y-3">
        {invoices.map((inv) => (
          <div key={inv.id} className="card flex flex-wrap justify-between gap-4">
            <div>
              <p className="font-semibold">{inv.invoice_number}</p>
              <p className="text-sm text-gray-600">
                Issued {formatDate(inv.issue_date)} · Due {formatDate(inv.due_date)}
              </p>
            </div>
            <div className="text-right">
              <p className="font-semibold">{formatGbp(inv.total_gbp)}</p>
              <span className={`badge ${statusBadgeClass(inv.status)}`}>{inv.status}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

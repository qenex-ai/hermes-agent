import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { formatDate, formatGbp, statusBadgeClass } from "@/lib/format";
import type { Invoice } from "@/lib/types";

export default async function InvoicesPage() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("invoices")
    .select("*, customers(name)")
    .order("issue_date", { ascending: false });

  const invoices = (data ?? []) as Invoice[];

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-harbor-900">Billing</h1>
          <p className="mt-2 text-gray-600">
            Invoice list, payment status · billing@harborlane.qenex.dev
          </p>
        </div>
        <Link href="/admin/invoices/new" className="btn-primary">
          New invoice
        </Link>
      </div>
      {error && (
        <p className="mt-4 rounded-lg bg-amber-50 p-4 text-sm text-amber-800">
          Staff authentication required to view invoices.
        </p>
      )}
      <div className="mt-6 overflow-x-auto rounded-xl border border-gray-200 bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b bg-gray-50 text-gray-600">
            <tr>
              <th className="px-4 py-3 font-medium">Invoice</th>
              <th className="px-4 py-3 font-medium">Customer</th>
              <th className="px-4 py-3 font-medium">Issued</th>
              <th className="px-4 py-3 font-medium">Due</th>
              <th className="px-4 py-3 font-medium">Total</th>
              <th className="px-4 py-3 font-medium">Paid</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr key={inv.id} className="border-b last:border-0">
                <td className="px-4 py-3 font-medium">{inv.invoice_number}</td>
                <td className="px-4 py-3">{inv.customers?.name ?? "—"}</td>
                <td className="px-4 py-3">{formatDate(inv.issue_date)}</td>
                <td className="px-4 py-3">{formatDate(inv.due_date)}</td>
                <td className="px-4 py-3">{formatGbp(inv.total_gbp)}</td>
                <td className="px-4 py-3">{formatGbp(inv.amount_paid_gbp)}</td>
                <td className="px-4 py-3">
                  <span className={`badge ${statusBadgeClass(inv.status)}`}>{inv.status}</span>
                </td>
              </tr>
            ))}
            {invoices.length === 0 && !error && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                  No invoices yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

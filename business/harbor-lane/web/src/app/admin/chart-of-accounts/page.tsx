import { createClient } from "@/lib/supabase/server";
import type { ChartAccount } from "@/lib/types";

export default async function ChartOfAccountsPage() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("chart_of_accounts")
    .select("*")
    .eq("is_active", true)
    .order("code");

  const accounts = (data ?? []) as ChartAccount[];

  return (
    <div>
      <h1 className="text-2xl font-bold text-harbor-900">Chart of accounts</h1>
      <p className="mt-2 text-gray-600">
        Xero-ready account codes. Map to Xero on first sync — codes align with standard UK
        SME structure.
      </p>
      {error && (
        <p className="mt-4 rounded-lg bg-amber-50 p-4 text-sm text-amber-800">
          Staff authentication required.
        </p>
      )}
      <div className="mt-6 overflow-x-auto rounded-xl border border-gray-200 bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b bg-gray-50 text-gray-600">
            <tr>
              <th className="px-4 py-3 font-medium">Code</th>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Tax type</th>
              <th className="px-4 py-3 font-medium">Xero ID</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id} className="border-b last:border-0">
                <td className="px-4 py-3 font-mono">{a.code}</td>
                <td className="px-4 py-3">{a.name}</td>
                <td className="px-4 py-3">{a.account_type}</td>
                <td className="px-4 py-3">{a.tax_type ?? "—"}</td>
                <td className="px-4 py-3 text-gray-400">{a.xero_account_id ?? "Pending sync"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

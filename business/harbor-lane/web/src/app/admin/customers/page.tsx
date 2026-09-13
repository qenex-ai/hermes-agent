import { createClient } from "@/lib/supabase/server";
import type { Customer } from "@/lib/types";

export default async function CustomersPage() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("customers")
    .select("*")
    .order("name");

  const customers = (data ?? []) as Customer[];

  return (
    <div>
      <h1 className="text-2xl font-bold text-harbor-900">Customers</h1>
      <p className="mt-2 text-gray-600">UK SME client accounts</p>
      {error && (
        <p className="mt-4 rounded-lg bg-amber-50 p-4 text-sm text-amber-800">
          Sign in as staff to view customers. RLS requires an authenticated profile with
          owner/admin/consultant role.
        </p>
      )}
      <div className="mt-6 overflow-x-auto rounded-xl border border-gray-200 bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b bg-gray-50 text-gray-600">
            <tr>
              <th className="px-4 py-3 font-medium">Company</th>
              <th className="px-4 py-3 font-medium">Industry</th>
              <th className="px-4 py-3 font-medium">Location</th>
              <th className="px-4 py-3 font-medium">Primary contact</th>
            </tr>
          </thead>
          <tbody>
            {customers.map((c) => (
              <tr key={c.id} className="border-b last:border-0">
                <td className="px-4 py-3 font-medium">{c.name}</td>
                <td className="px-4 py-3">{c.industry ?? "—"}</td>
                <td className="px-4 py-3">{c.city ?? "—"}</td>
                <td className="px-4 py-3">
                  {c.primary_contact_name}
                  <br />
                  <span className="text-gray-500">{c.primary_contact_email}</span>
                </td>
              </tr>
            ))}
            {customers.length === 0 && !error && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                  No customers yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

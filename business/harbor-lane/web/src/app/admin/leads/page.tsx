import { createClient } from "@/lib/supabase/server";
import { formatGbp, statusBadgeClass } from "@/lib/format";
import type { Lead } from "@/lib/types";

export default async function LeadsPage() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("leads")
    .select("*")
    .order("created_at", { ascending: false });

  const leads = (data ?? []) as Lead[];

  return (
    <div>
      <h1 className="text-2xl font-bold text-harbor-900">Leads</h1>
      <p className="mt-2 text-gray-600">Inbound pipeline — qualify, propose, convert</p>
      {error && (
        <p className="mt-4 rounded-lg bg-amber-50 p-4 text-sm text-amber-800">
          Staff authentication required to view leads.
        </p>
      )}
      <div className="mt-6 grid gap-4">
        {leads.map((lead) => (
          <div key={lead.id} className="card flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="font-semibold">{lead.company_name}</h2>
              <p className="text-sm text-gray-600">
                {lead.contact_name} · {lead.contact_email}
              </p>
              {lead.source && (
                <p className="mt-1 text-xs text-gray-500">Source: {lead.source}</p>
              )}
            </div>
            <div className="text-right">
              <span className={`badge ${statusBadgeClass(lead.status)}`}>{lead.status}</span>
              {lead.estimated_value_gbp != null && (
                <p className="mt-2 text-sm font-medium">{formatGbp(lead.estimated_value_gbp)}</p>
              )}
            </div>
          </div>
        ))}
        {leads.length === 0 && !error && (
          <p className="text-center text-gray-500">No leads in pipeline</p>
        )}
      </div>
    </div>
  );
}

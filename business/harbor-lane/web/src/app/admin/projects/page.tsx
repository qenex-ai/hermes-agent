import { createClient } from "@/lib/supabase/server";
import { formatGbp, statusBadgeClass } from "@/lib/format";
import type { Project } from "@/lib/types";

export default async function ProjectsPage() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("projects")
    .select("*, customers(name)")
    .order("created_at", { ascending: false });

  const projects = (data ?? []) as Project[];

  return (
    <div>
      <h1 className="text-2xl font-bold text-harbor-900">Projects</h1>
      <p className="mt-2 text-gray-600">Active retainers and fixed-price engagements</p>
      {error && (
        <p className="mt-4 rounded-lg bg-amber-50 p-4 text-sm text-amber-800">
          Staff authentication required.
        </p>
      )}
      <div className="mt-6 grid gap-4">
        {projects.map((p) => (
          <div key={p.id} className="card">
            <div className="flex flex-wrap justify-between gap-2">
              <div>
                <h2 className="font-semibold">{p.name}</h2>
                <p className="text-sm text-gray-600">{p.customers?.name}</p>
              </div>
              <div className="flex gap-2">
                <span className="badge bg-harbor-100 text-harbor-800">{p.project_type}</span>
                <span className={`badge ${statusBadgeClass(p.status)}`}>{p.status}</span>
              </div>
            </div>
            <p className="mt-2 text-sm">
              Budget: {p.budget_gbp != null ? formatGbp(p.budget_gbp) : "—"}
              {p.monthly_retainer_gbp != null && (
                <> · Retainer: {formatGbp(p.monthly_retainer_gbp)}/mo</>
              )}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

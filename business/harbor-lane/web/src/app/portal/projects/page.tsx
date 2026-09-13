import { createClient } from "@/lib/supabase/server";
import { formatGbp, statusBadgeClass } from "@/lib/format";
import type { Project } from "@/lib/types";

export default async function PortalProjectsPage() {
  const supabase = await createClient();
  const { data, error } = await supabase.from("projects").select("*").order("start_date", { ascending: false });
  const projects = (data ?? []) as Project[];

  return (
    <div>
      <h1 className="text-2xl font-bold text-harbor-900">Your projects</h1>
      {error && (
        <p className="mt-4 rounded-lg bg-amber-50 p-4 text-sm text-amber-800">
          Sign in with your client account to view projects.
        </p>
      )}
      <div className="mt-6 space-y-4">
        {projects.map((p) => (
          <div key={p.id} className="card">
            <div className="flex justify-between">
              <h2 className="font-semibold">{p.name}</h2>
              <span className={`badge ${statusBadgeClass(p.status)}`}>{p.status}</span>
            </div>
            <p className="mt-2 text-sm capitalize text-gray-600">{p.project_type.replace("_", " ")}</p>
            {p.monthly_retainer_gbp != null && (
              <p className="mt-1 text-sm">Retainer: {formatGbp(p.monthly_retainer_gbp)}/month</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

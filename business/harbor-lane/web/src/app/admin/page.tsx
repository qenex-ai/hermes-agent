import Link from "next/link";
import { createClient } from "@/lib/supabase/server";

export default async function AdminDashboard() {
  const supabase = await createClient();

  const [customers, leads, invoices, projects] = await Promise.all([
    supabase.from("customers").select("id", { count: "exact", head: true }),
    supabase.from("leads").select("id", { count: "exact", head: true }),
    supabase.from("invoices").select("id", { count: "exact", head: true }),
    supabase.from("projects").select("id", { count: "exact", head: true }),
  ]);

  const stats = [
    { label: "Customers", count: customers.count ?? 0, href: "/admin/customers" },
    { label: "Open leads", count: leads.count ?? 0, href: "/admin/leads" },
    { label: "Invoices", count: invoices.count ?? 0, href: "/admin/invoices" },
    { label: "Projects", count: projects.count ?? 0, href: "/admin/projects" },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold text-harbor-900">Staff admin</h1>
      <p className="mt-2 text-gray-600">
        Day-one operations: CRM, billing, and client delivery. Sign in with your staff account
        to access live data (RLS enforced).
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <Link key={s.label} href={s.href} className="card transition hover:border-harbor-300">
            <p className="text-sm text-gray-500">{s.label}</p>
            <p className="mt-1 text-3xl font-bold text-harbor-800">{s.count}</p>
          </Link>
        ))}
      </div>
      <div className="mt-8 card">
        <h2 className="font-semibold">Quick actions</h2>
        <ul className="mt-4 space-y-2 text-sm">
          <li>
            <Link href="/admin/invoices/new" className="text-harbor-700 underline">
              Create invoice
            </Link>
          </li>
          <li>
            <Link href="/admin/leads" className="text-harbor-700 underline">
              Review lead pipeline
            </Link>
          </li>
          <li>
            <a href="mailto:support@harborlane.qenex.dev" className="text-harbor-700 underline">
              Answer support@ (IMAP)
            </a>
          </li>
        </ul>
      </div>
    </div>
  );
}

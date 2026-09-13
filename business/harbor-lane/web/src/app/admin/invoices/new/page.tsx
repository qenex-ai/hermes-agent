"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

export default function NewInvoicePage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const form = new FormData(e.currentTarget);
    const supabase = createClient();

    const { data: firm } = await supabase
      .from("firms")
      .select("id")
      .eq("slug", "harbor-lane")
      .single();

    if (!firm) {
      setError("Firm not found or access denied. Sign in as staff.");
      setLoading(false);
      return;
    }

    const subtotal = Number(form.get("subtotal"));
    const vat = subtotal * 0.2;
    const total = subtotal + vat;

    const { error: insertError } = await supabase.from("invoices").insert({
      firm_id: firm.id,
      customer_id: form.get("customer_id"),
      invoice_number: form.get("invoice_number"),
      status: "draft",
      issue_date: form.get("issue_date"),
      due_date: form.get("due_date"),
      subtotal_gbp: subtotal,
      vat_gbp: vat,
      total_gbp: total,
      notes: form.get("notes") || null,
    });

    if (insertError) {
      setError(insertError.message);
      setLoading(false);
      return;
    }

    router.push("/admin/invoices");
    router.refresh();
  }

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-bold text-harbor-900">Create invoice</h1>
      <p className="mt-2 text-sm text-gray-600">
        Draft an invoice for a client. Mark as sent from the invoice list when ready.
      </p>
      <form onSubmit={(e) => void handleSubmit(e)} className="mt-6 space-y-4 card">
        <label className="block text-sm">
          Customer ID
          <input
            name="customer_id"
            required
            className="mt-1 w-full rounded-lg border px-3 py-2"
            placeholder="UUID from customers table"
          />
        </label>
        <label className="block text-sm">
          Invoice number
          <input
            name="invoice_number"
            required
            className="mt-1 w-full rounded-lg border px-3 py-2"
            placeholder="HL-2026-002"
          />
        </label>
        <label className="block text-sm">
          Subtotal (ex VAT, GBP)
          <input
            name="subtotal"
            type="number"
            step="0.01"
            required
            className="mt-1 w-full rounded-lg border px-3 py-2"
          />
        </label>
        <label className="block text-sm">
          Issue date
          <input
            name="issue_date"
            type="date"
            required
            defaultValue={new Date().toISOString().slice(0, 10)}
            className="mt-1 w-full rounded-lg border px-3 py-2"
          />
        </label>
        <label className="block text-sm">
          Due date
          <input
            name="due_date"
            type="date"
            required
            className="mt-1 w-full rounded-lg border px-3 py-2"
          />
        </label>
        <label className="block text-sm">
          Notes
          <textarea name="notes" rows={3} className="mt-1 w-full rounded-lg border px-3 py-2" />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button type="submit" disabled={loading} className="btn-primary disabled:opacity-50">
          {loading ? "Saving…" : "Save draft invoice"}
        </button>
      </form>
    </div>
  );
}

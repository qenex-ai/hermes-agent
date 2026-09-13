import { createClient } from "@/lib/supabase/server";
import { formatDate } from "@/lib/format";
import type { Message } from "@/lib/types";

export default async function PortalMessagesPage() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("messages")
    .select("*")
    .order("created_at", { ascending: false });
  const messages = (data ?? []) as Message[];

  return (
    <div>
      <h1 className="text-2xl font-bold text-harbor-900">Messages</h1>
      <p className="mt-2 text-sm text-gray-600">
        Portal messages with your account team. For urgent issues email{" "}
        <a href="mailto:support@harborlane.qenex.dev" className="text-harbor-700 underline">
          support@harborlane.qenex.dev
        </a>
      </p>
      {error && (
        <p className="mt-4 rounded-lg bg-amber-50 p-4 text-sm text-amber-800">
          Sign in to view and send messages.
        </p>
      )}
      <div className="mt-6 space-y-4">
        {messages.map((m) => (
          <div key={m.id} className="card">
            <div className="flex justify-between text-sm">
              <span className="font-medium">{m.subject}</span>
              <span className="text-gray-500">{formatDate(m.created_at)}</span>
            </div>
            <p className="mt-2 text-sm text-gray-700">{m.body}</p>
            <p className="mt-2 text-xs text-gray-400">
              {m.is_from_client ? "From you" : "From Harbor Lane"}
            </p>
          </div>
        ))}
        {messages.length === 0 && !error && (
          <p className="text-gray-500">No messages yet.</p>
        )}
      </div>
    </div>
  );
}

export function formatGbp(amount: number): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
  }).format(amount);
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(iso));
}

export function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    sent: "bg-blue-100 text-blue-800",
    paid: "bg-green-100 text-green-800",
    overdue: "bg-red-100 text-red-800",
    draft: "bg-gray-100 text-gray-700",
    active: "bg-green-100 text-green-800",
    qualified: "bg-amber-100 text-amber-800",
    proposal: "bg-purple-100 text-purple-800",
    new: "bg-sky-100 text-sky-800",
  };
  return map[status] ?? "bg-gray-100 text-gray-700";
}

import Link from "next/link";

export default function PortalHome() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-harbor-900">Client portal</h1>
      <p className="mt-2 text-gray-600">
        View your projects, invoices, and messages with Harbor Lane Advisory.
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        <Link href="/portal/projects" className="card transition hover:border-harbor-300">
          <h2 className="font-semibold">Projects</h2>
          <p className="mt-2 text-sm text-gray-600">Active jobs and retainers</p>
        </Link>
        <Link href="/portal/invoices" className="card transition hover:border-harbor-300">
          <h2 className="font-semibold">Invoices</h2>
          <p className="mt-2 text-sm text-gray-600">Payment status and history</p>
        </Link>
        <Link href="/portal/messages" className="card transition hover:border-harbor-300">
          <h2 className="font-semibold">Messages</h2>
          <p className="mt-2 text-sm text-gray-600">Contact your account team</p>
        </Link>
      </div>
      <p className="mt-8 text-sm text-gray-500">
        Sign in with your client credentials to access your data. Contact{" "}
        <a href="mailto:support@harborlane.qenex.dev" className="text-harbor-700 underline">
          support@harborlane.qenex.dev
        </a>{" "}
        for access.
      </p>
    </div>
  );
}

import Link from "next/link";

interface SiteHeaderProps {
  variant?: "marketing" | "portal" | "admin";
}

export function SiteHeader({ variant = "marketing" }: SiteHeaderProps) {
  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-harbor-700 text-sm font-bold text-white">
            HL
          </span>
          <span className="font-semibold text-harbor-900">Harbor Lane Advisory</span>
        </Link>
        <nav className="flex items-center gap-6 text-sm">
          {variant === "marketing" && (
            <>
              <Link href="/#services" className="text-gray-600 hover:text-harbor-700">
                Services
              </Link>
              <Link href="/#approach" className="text-gray-600 hover:text-harbor-700">
                Approach
              </Link>
              <Link href="/support" className="text-gray-600 hover:text-harbor-700">
                Support
              </Link>
              <Link href="/portal" className="btn-secondary">
                Client portal
              </Link>
              <Link href="/admin" className="text-gray-500 hover:text-harbor-700">
                Staff
              </Link>
            </>
          )}
          {variant === "portal" && (
            <>
              <Link href="/portal/projects" className="text-gray-600 hover:text-harbor-700">
                Projects
              </Link>
              <Link href="/portal/invoices" className="text-gray-600 hover:text-harbor-700">
                Invoices
              </Link>
              <Link href="/portal/messages" className="text-gray-600 hover:text-harbor-700">
                Messages
              </Link>
              <Link href="/" className="text-gray-500 hover:text-harbor-700">
                Home
              </Link>
            </>
          )}
          {variant === "admin" && (
            <>
              <Link href="/admin/customers" className="text-gray-600 hover:text-harbor-700">
                Customers
              </Link>
              <Link href="/admin/leads" className="text-gray-600 hover:text-harbor-700">
                Leads
              </Link>
              <Link href="/admin/invoices" className="text-gray-600 hover:text-harbor-700">
                Billing
              </Link>
              <Link href="/admin/chart-of-accounts" className="text-gray-600 hover:text-harbor-700">
                Chart of accounts
              </Link>
              <Link href="/" className="text-gray-500 hover:text-harbor-700">
                Home
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}

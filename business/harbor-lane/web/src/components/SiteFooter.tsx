import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-gray-200 bg-white">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 md:grid-cols-3">
        <div>
          <p className="font-semibold text-harbor-900">Harbor Lane Advisory Ltd</p>
          <p className="mt-2 text-sm text-gray-600">
            71-75 Shelton Street, Covent Garden
            <br />
            London WC2H 9JQ
          </p>
          <p className="mt-2 text-sm text-gray-600">
            <a href="mailto:hello@harborlane.qenex.dev" className="hover:text-harbor-700">
              hello@harborlane.qenex.dev
            </a>
          </p>
        </div>
        <div>
          <p className="font-medium text-harbor-900">Contact</p>
          <ul className="mt-2 space-y-1 text-sm text-gray-600">
            <li>
              <a href="mailto:support@harborlane.qenex.dev">support@harborlane.qenex.dev</a>
            </li>
            <li>
              <a href="mailto:billing@harborlane.qenex.dev">billing@harborlane.qenex.dev</a>
            </li>
            <li>+44 20 7946 0958</li>
          </ul>
        </div>
        <div>
          <p className="font-medium text-harbor-900">Legal</p>
          <ul className="mt-2 space-y-1 text-sm text-gray-600">
            <li>
              <Link href="/privacy" className="hover:text-harbor-700">
                Privacy policy
              </Link>
            </li>
            <li>
              <Link href="/terms" className="hover:text-harbor-700">
                Terms of service
              </Link>
            </li>
            <li>
              <Link href="/cookies" className="hover:text-harbor-700">
                Cookie policy
              </Link>
            </li>
            <li>
              <Link href="/support" className="hover:text-harbor-700">
                Support
              </Link>
            </li>
          </ul>
        </div>
      </div>
      <div className="border-t border-gray-100 py-4 text-center text-xs text-gray-500">
        © {new Date().getFullYear()} Harbor Lane Advisory Ltd. Registered in England & Wales.
      </div>
    </footer>
  );
}

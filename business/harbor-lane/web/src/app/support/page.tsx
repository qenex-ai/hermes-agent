import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";

export default function SupportPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="mx-auto max-w-3xl flex-1 px-4 py-12">
        <h1 className="text-3xl font-bold text-harbor-900">Support</h1>
        <p className="mt-4 text-gray-600">
          We aim to respond to all client enquiries within one business day.
        </p>

        <section id="contact" className="mt-10 card">
          <h2 className="text-lg font-semibold">Contact us</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div>
              <dt className="font-medium text-gray-700">General enquiries</dt>
              <dd>
                <a href="mailto:hello@harborlane.qenex.dev" className="text-harbor-700">
                  hello@harborlane.qenex.dev
                </a>
              </dd>
            </div>
            <div>
              <dt className="font-medium text-gray-700">Client support</dt>
              <dd>
                <a href="mailto:support@harborlane.qenex.dev" className="text-harbor-700">
                  support@harborlane.qenex.dev
                </a>
              </dd>
            </div>
            <div>
              <dt className="font-medium text-gray-700">Billing</dt>
              <dd>
                <a href="mailto:billing@harborlane.qenex.dev" className="text-harbor-700">
                  billing@harborlane.qenex.dev
                </a>
              </dd>
            </div>
            <div>
              <dt className="font-medium text-gray-700">Phone</dt>
              <dd>+44 20 7946 0958 (Mon–Fri, 9am–5pm UK)</dd>
            </div>
          </dl>
        </section>

        <section className="mt-8 card">
          <h2 className="text-lg font-semibold">Client portal</h2>
          <p className="mt-2 text-sm text-gray-600">
            Existing clients can view projects, invoices, and messages at{" "}
            <a href="/portal" className="text-harbor-700 underline">
              harborlane.qenex.dev/portal
            </a>
            .
          </p>
        </section>

        <section className="mt-8 card">
          <h2 className="text-lg font-semibold">Service levels</h2>
          <ul className="mt-2 list-inside list-disc text-sm text-gray-600">
            <li>Retainer clients: same-day response for priority items</li>
            <li>Project clients: response within 1 business day</li>
            <li>Billing queries: billing@, response within 2 business days</li>
          </ul>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

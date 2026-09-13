import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";

export default function TermsPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="prose prose-sm mx-auto max-w-3xl flex-1 px-4 py-12">
        <h1>Terms of Service</h1>
        <p className="text-gray-600">Last updated: 13 September 2026</p>
        <p>
          These terms govern use of Harbor Lane Advisory Ltd&apos;s website, client portal, and
          professional services delivered to UK businesses.
        </p>
        <h2>Services</h2>
        <p>
          We provide advisory, operational, and project-based professional services under
          separately agreed statements of work or retainer agreements. Scope and fees are
          defined in writing before work begins.
        </p>
        <h2>Fees and payment</h2>
        <p>
          Invoices are issued in GBP and are due within 30 days unless otherwise agreed. VAT
          is charged where applicable. Late payment may incur interest under the Late Payment
          of Commercial Debts (Interest) Act 1998.
        </p>
        <h2>Confidentiality</h2>
        <p>
          Both parties agree to keep confidential information private except as required by law
          or with written consent.
        </p>
        <h2>Liability</h2>
        <p>
          Our liability is limited to the fees paid for the relevant engagement, except where
          exclusion is prohibited by law. We do not provide legal, tax, or regulated financial
          advice unless explicitly agreed in writing.
        </p>
        <h2>Governing law</h2>
        <p>These terms are governed by the laws of England and Wales.</p>
        <p>
          Contact:{" "}
          <a href="mailto:hello@harborlane.qenex.dev">hello@harborlane.qenex.dev</a>
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}

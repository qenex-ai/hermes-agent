import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";

export default function PrivacyPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="prose prose-sm mx-auto max-w-3xl flex-1 px-4 py-12">
        <h1>Privacy Policy</h1>
        <p className="text-gray-600">Last updated: 13 September 2026</p>
        <p>
          Harbor Lane Advisory Ltd (&quot;we&quot;, &quot;us&quot;) is a UK professional services firm
          registered in England and Wales. This policy explains how we collect and use personal
          data when you use our website, client portal, and services.
        </p>
        <h2>Data we collect</h2>
        <ul>
          <li>Contact details (name, email, phone, company)</li>
          <li>Client engagement and billing records</li>
          <li>Portal usage and message content</li>
          <li>Technical logs (IP address, browser type) for security</li>
        </ul>
        <h2>Lawful basis</h2>
        <p>
          We process data under contract (delivering services), legitimate interests (operating
          our business), and consent where required (marketing cookies).
        </p>
        <h2>Data storage</h2>
        <p>
          Client data is stored in Supabase (eu-west-2, London) with row-level security. Email
          is hosted on QENEX infrastructure with TLS in transit.
        </p>
        <h2>Your rights</h2>
        <p>
          Under UK GDPR you may request access, correction, erasure, or portability. Contact{" "}
          <a href="mailto:hello@harborlane.qenex.dev">hello@harborlane.qenex.dev</a>. You may
          complain to the ICO at ico.org.uk.
        </p>
        <h2>ICO registration</h2>
        <p>
          ICO registration is maintained on the founder&apos;s external compliance track — not
          filed via QENEX automation.
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}

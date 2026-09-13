import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";

export default function CookiesPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="prose prose-sm mx-auto max-w-3xl flex-1 px-4 py-12">
        <h1>Cookie Policy</h1>
        <p className="text-gray-600">Last updated: 13 September 2026</p>
        <p>
          Harbor Lane Advisory uses cookies and similar technologies on harborlane.qenex.dev
          and our client portal.
        </p>
        <h2>Essential cookies</h2>
        <p>
          Required for authentication, session management, and security. These cannot be
          disabled while using the portal.
        </p>
        <h2>Analytics</h2>
        <p>
          We do not use third-party advertising trackers. Optional privacy-respecting analytics
          may be enabled after explicit consent.
        </p>
        <h2>Managing cookies</h2>
        <p>
          You can control cookies through your browser settings. Disabling essential cookies may
          prevent portal login.
        </p>
        <p>
          Questions:{" "}
          <a href="mailto:hello@harborlane.qenex.dev">hello@harborlane.qenex.dev</a>
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}

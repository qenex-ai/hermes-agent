import Link from "next/link";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main>
        <section className="bg-gradient-to-br from-harbor-950 via-harbor-800 to-harbor-600 px-4 py-20 text-white">
          <div className="mx-auto max-w-4xl text-center">
            <p className="text-sm font-medium uppercase tracking-wider text-harbor-200">
              London · UK SMEs
            </p>
            <h1 className="mt-4 text-4xl font-bold tracking-tight md:text-5xl">
              Retainers and project work that keep your business moving
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-harbor-100">
              Harbor Lane Advisory partners with growing UK businesses on operations,
              finance, and strategic delivery — through monthly retainers or fixed-scope
              projects.
            </p>
            <div className="mt-10 flex flex-wrap justify-center gap-4">
              <Link href="/support#contact" className="btn-primary bg-white text-harbor-800 hover:bg-harbor-50">
                Book a discovery call
              </Link>
              <Link href="/portal" className="btn-secondary border-white/30 text-white hover:bg-white/10">
                Client portal login
              </Link>
            </div>
          </div>
        </section>

        <section id="services" className="mx-auto max-w-6xl px-4 py-16">
          <h2 className="text-2xl font-bold text-harbor-900">What we deliver</h2>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {[
              {
                title: "Monthly retainers",
                body: "Embedded advisory for finance, ops, and leadership — predictable scope, predictable fees.",
              },
              {
                title: "Fixed-price projects",
                body: "Defined outcomes with clear milestones: process redesign, due diligence, board packs.",
              },
              {
                title: "Time & materials",
                body: "Flexible capacity for surge work, interim cover, or specialist analysis.",
              },
            ].map((s) => (
              <div key={s.title} className="card">
                <h3 className="font-semibold text-harbor-800">{s.title}</h3>
                <p className="mt-2 text-sm text-gray-600">{s.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="approach" className="bg-harbor-50 px-4 py-16">
          <div className="mx-auto max-w-6xl">
            <h2 className="text-2xl font-bold text-harbor-900">How we work</h2>
            <ol className="mt-8 grid gap-6 md:grid-cols-4">
              {[
                ["Discover", "We map your constraints, stakeholders, and success criteria."],
                ["Propose", "Clear scope, fees, and timeline — retainer or project."],
                ["Deliver", "Weekly cadence, shared portal, and direct access to your team."],
                ["Invoice", "Transparent billing with VAT-ready invoices and payment tracking."],
              ].map(([step, desc], i) => (
                <li key={step} className="card">
                  <span className="text-xs font-bold text-harbor-500">Step {i + 1}</span>
                  <h3 className="mt-1 font-semibold">{step}</h3>
                  <p className="mt-2 text-sm text-gray-600">{desc}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-16 text-center">
          <h2 className="text-2xl font-bold text-harbor-900">Ready to talk?</h2>
          <p className="mx-auto mt-4 max-w-xl text-gray-600">
            Email{" "}
            <a href="mailto:hello@harborlane.qenex.dev" className="text-harbor-700 underline">
              hello@harborlane.qenex.dev
            </a>{" "}
            or reach support at{" "}
            <a href="mailto:support@harborlane.qenex.dev" className="text-harbor-700 underline">
              support@harborlane.qenex.dev
            </a>
            .
          </p>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

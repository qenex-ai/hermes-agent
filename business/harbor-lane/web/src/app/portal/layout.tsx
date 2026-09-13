import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader variant="portal" />
      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">{children}</main>
      <SiteFooter />
    </div>
  );
}

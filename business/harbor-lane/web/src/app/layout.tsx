import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Harbor Lane Advisory — Professional services for UK SMEs",
    template: "%s | Harbor Lane Advisory",
  },
  description:
    "London-based professional services firm delivering retainers and project work to UK SMEs. Operations, finance, and growth advisory.",
  metadataBase: new URL("https://harborlane.qenex.dev"),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB">
      <body className="min-h-screen font-sans antialiased">{children}</body>
    </html>
  );
}

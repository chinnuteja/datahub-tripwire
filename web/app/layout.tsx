import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "localhost:3000";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  const origin = `${protocol}://${host}`;

  return {
    metadataBase: new URL(origin),
    title: "Tripwire — Data systems that remember",
    description:
      "Adaptive change safety for data, ML, and AI systems, powered by DataHub context and executable evidence.",
    icons: { icon: "/og.png", shortcut: "/og.png" },
    openGraph: {
      title: "Tripwire — Data systems that remember",
      description: "Trace. Test. Witness. Act. Immunize. Powered by DataHub.",
      type: "website",
      url: origin,
      images: [{ url: `${origin}/og.png`, width: 1672, height: 941, alt: "Tripwire evidence chain blocking a learned data regression" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "Tripwire — Data systems that remember",
      description: "An adaptive change-safety agent powered by DataHub.",
      images: [`${origin}/og.png`],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Navbar from "@/components/Navbar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const viewport: Viewport = {
  themeColor: "#08080a",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_APP_URL || "https://jhunt.vercel.app"
  ),
  title: {
    default: "JHunt: Thailand Tech Market Intelligence & AI Blueprint Hub",
    template: "%s | JHunt",
  },
  description:
    "Production portfolio architecture specifications reverse-engineered from live Thailand tech demand signals across JobsDB, Blognone, and JobThai.",
  keywords: [
    "Thailand tech jobs",
    "Bangkok software engineering",
    "tech stack demand",
    "system architecture blueprints",
    "portfolio specs",
    "salary benchmarks Thailand",
  ],
  authors: [{ name: "JHunt Telemetry Engine" }],
  creator: "JHunt",
  publisher: "JHunt",
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "/",
    siteName: "JHunt",
    title: "JHunt: Thailand Tech Market Intelligence & AI Blueprint Hub",
    description:
      "Production portfolio architecture specifications reverse-engineered from live Thailand tech demand signals.",
  },
  twitter: {
    card: "summary_large_image",
    title: "JHunt: Thailand Tech Market Intelligence & AI Blueprint Hub",
    description:
      "Production portfolio architecture specifications reverse-engineered from live Thailand tech demand signals.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} dark antialiased`}
    >
      <body className="min-h-screen bg-[#08080a] text-zinc-100 flex flex-col font-sans selection:bg-cyan-500/25 selection:text-cyan-200 relative overflow-x-hidden">
        {/* Subtle Ambient Top Light Beam */}
        <div
          className="pointer-events-none fixed top-0 left-1/2 -translate-x-1/2 w-full max-w-6xl h-[480px] bg-gradient-to-b from-cyan-500/[0.07] via-indigo-500/[0.03] to-transparent blur-3xl -z-10"
          aria-hidden="true"
        />
        <Navbar />
        <div className="flex-1 flex flex-col">{children}</div>
      </body>
    </html>
  );
}

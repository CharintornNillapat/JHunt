import type { Metadata } from "next";
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

export const metadata: Metadata = {
  title: "JHunt | Market Intelligence & AI Blueprint Hub",
  description:
    "Deterministic portfolio architecture specifications derived from live Thailand tech demand signals.",
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

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Terminal, BarChart3, Layers } from "lucide-react";
import { cn } from "@/lib/utils";

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg
      role="img"
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
    >
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

export default function Navbar() {
  const pathname = usePathname();

  const navItems = [
    { href: "/", label: "Blueprints", icon: Layers },
    { href: "/analytics", label: "Market Analytics", icon: BarChart3 },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/[0.07] bg-[#08080a]/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand / Logo */}
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-cyan-500 via-sky-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition-transform duration-200">
              <Terminal className="h-4.5 w-4.5 text-white" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-base tracking-tight bg-gradient-to-r from-white via-zinc-200 to-zinc-400 bg-clip-text text-transparent">
                JHunt
              </span>
              <span className="text-[10px] tracking-wider font-mono text-zinc-500 uppercase -mt-0.5">
                Obsidian Hub // V2
              </span>
            </div>
          </Link>

          {/* Navigation Links with animated active pill */}
          <nav className="hidden md:flex items-center gap-1.5 p-1 rounded-lg bg-zinc-900/60 border border-white/[0.06]">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "relative flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-medium transition-colors duration-200",
                    isActive ? "text-cyan-300" : "text-zinc-400 hover:text-zinc-200"
                  )}
                >
                  {isActive && (
                    <motion.span
                      layoutId="activeNavPill"
                      className="absolute inset-0 rounded-md bg-cyan-950/70 border border-cyan-500/30 shadow-sm"
                      transition={{ type: "spring", stiffness: 260, damping: 25 }}
                    />
                  )}
                  <Icon className="h-3.5 w-3.5 relative z-10" />
                  <span className="relative z-10">{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Live System Telemetry Indicator & GitHub */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-900/90 border border-emerald-500/20 text-emerald-400 text-[11px] font-mono shadow-inner">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            <span className="tracking-wide font-medium">PIPELINE IDLE / CRON 08:00 ICT</span>
          </div>

          <a
            href="https://github.com/CharintornNillapat/JHunt"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-zinc-900/80 border border-white/[0.08] hover:border-zinc-700 text-zinc-300 hover:text-white transition-all text-xs font-medium"
          >
            <GithubIcon className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">GitHub</span>
          </a>
        </div>
      </div>
    </header>
  );
}

import Link from "next/link";
import {
  ArrowRight,
  Briefcase,
  Calendar,
  Code2,
  Cpu,
  Layers,
  Sparkles,
  Terminal,
} from "lucide-react";
import { getAllProjects, parseTechStack } from "@/lib/turso";

export const revalidate = 60;

function formatDate(dateStr: string): string {
  if (!dateStr) return "Recent";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export default async function HomePage() {
  const projects = await getAllProjects();

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      {/* Top Navigation */}
      <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition-transform">
              <Terminal className="h-5 w-5 text-white" />
            </div>
            <div>
              <span className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-cyan-400 via-teal-300 to-blue-500 bg-clip-text text-transparent">
                JHunt
              </span>
              <span className="text-xs text-slate-400 ml-2 hidden sm:inline font-mono">
                / Blueprint Catalog
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-4 text-xs">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-slate-400">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span>Turso Cloud Sync</span>
            </div>
            <a
              href="https://github.com/CharintornNillapat/JHunt"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 hover:text-cyan-400 transition-colors font-medium"
            >
              GitHub &rarr;
            </a>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden border-b border-slate-800/60 bg-gradient-to-b from-slate-900/50 via-slate-950 to-slate-950 py-12 sm:py-16">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(6,182,212,0.15),rgba(255,255,255,0))] pointer-events-none" />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-950/60 border border-cyan-800/50 text-cyan-400 text-xs font-medium mb-4">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Real-World Market Intelligence</span>
            </div>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white mb-4">
              Production Portfolio{" "}
              <span className="bg-gradient-to-r from-cyan-400 via-teal-300 to-blue-500 bg-clip-text text-transparent">
                Architecture Blueprints
              </span>
            </h1>
            <p className="text-slate-400 text-base sm:text-lg leading-relaxed">
              Every system architecture and coding blueprint here is synthesized directly from live tech job requirements in Thailand. Built to prove production readiness to hiring leads.
            </p>
          </div>
        </div>
      </section>

      {/* Main Content Catalog */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex-1 w-full">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-cyan-400" />
            <h2 className="text-xl font-bold text-white tracking-tight">
              Curated Architecture Blueprints
            </h2>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">
              {projects.length}
            </span>
          </div>
        </div>

        {projects.length === 0 ? (
          /* Empty State */
          <div className="border border-dashed border-slate-800 rounded-2xl p-12 text-center bg-slate-900/30 max-w-xl mx-auto my-12">
            <div className="h-14 w-14 rounded-2xl bg-slate-800/80 border border-slate-700/60 flex items-center justify-center mx-auto mb-4 text-cyan-400">
              <Cpu className="h-7 w-7" />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">
              No Blueprints Synchronized Yet
            </h3>
            <p className="text-slate-400 text-sm mb-6 leading-relaxed">
              Run the scraper and market ideation engine to analyze active job descriptions and automatically generate blueprints to Turso Cloud.
            </p>
            <div className="bg-slate-950 border border-slate-800/80 rounded-lg p-3 font-mono text-xs text-cyan-300 inline-block text-left">
              $ python main.py run --all
            </div>
          </div>
        ) : (
          /* Card Grid */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((proj) => {
              const techList = parseTechStack(proj.tech_stack);

              return (
                <Link
                  key={proj.id}
                  href={`/blueprints/${proj.id}`}
                  className="group relative flex flex-col justify-between rounded-xl border border-slate-800/80 bg-slate-900/40 p-6 hover:border-cyan-500/50 hover:bg-slate-900/80 hover:shadow-xl hover:shadow-cyan-500/10 transition-all duration-300"
                >
                  <div>
                    {/* Role & Date Bar */}
                    <div className="flex items-center justify-between gap-2 mb-3.5">
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-cyan-950/70 border border-cyan-800/60 text-cyan-300">
                        {proj.role || "Software Engineer"}
                      </span>
                      <div className="flex items-center gap-1.5 text-xs text-slate-500 font-mono">
                        <Calendar className="h-3.5 w-3.5" />
                        <span>{formatDate(proj.created_at)}</span>
                      </div>
                    </div>

                    {/* Title */}
                    <h3 className="text-lg font-bold text-slate-100 group-hover:text-cyan-400 transition-colors line-clamp-2 mb-2.5">
                      {proj.title}
                    </h3>

                    {/* Domain / Industry */}
                    {proj.domain && (
                      <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-4">
                        <Briefcase className="h-3.5 w-3.5 text-slate-500 shrink-0" />
                        <span className="line-clamp-1">{proj.domain}</span>
                      </div>
                    )}

                    {/* Tech Stack Chips */}
                    {techList.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mb-6">
                        {techList.slice(0, 6).map((tech, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-mono bg-slate-950/80 border border-slate-800 text-slate-300"
                          >
                            <Code2 className="h-3 w-3 text-cyan-500/70" />
                            {tech}
                          </span>
                        ))}
                        {techList.length > 6 && (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-xs font-mono text-slate-500">
                            +{techList.length - 6} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Card Footer CTA */}
                  <div className="pt-4 border-t border-slate-800/60 flex items-center justify-between text-xs text-slate-400 group-hover:text-cyan-400 font-medium transition-colors">
                    <span>View Architecture Spec</span>
                    <ArrowRight className="h-4 w-4 transform group-hover:translate-x-1 transition-transform" />
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950/60 py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4">
          JHunt Market Intelligence System &bull; Powered by Next.js &amp; Turso Cloud
        </div>
      </footer>
    </div>
  );
}

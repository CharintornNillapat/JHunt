import { getAllProjects } from "@/lib/turso";
import BlueprintCatalog from "@/components/BlueprintCatalog";
import { Cpu, Database, Activity } from "lucide-react";


export const revalidate = 60;

export default async function HomePage() {
  const projects = await getAllProjects();

  return (
    <div className="flex-1 flex flex-col">
      {/* Hero Section */}
      <section className="relative overflow-hidden border-b border-white/[0.08] bg-gradient-to-b from-zinc-950 via-zinc-900/40 to-zinc-950 py-16 sm:py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
          <div className="max-w-3xl">
            {/* Monospace Badge */}
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-cyan-950/60 border border-cyan-500/30 text-cyan-300 text-[11px] font-mono tracking-wide mb-5 shadow-sm">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan-400"></span>
              </span>
              <span>LIVE TECH INGESTION ENGINE</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white mb-5 leading-tight">
              Deterministic Portfolio{" "}
              <span className="bg-gradient-to-r from-cyan-400 via-sky-300 to-indigo-400 bg-clip-text text-transparent">
                Architecture Blueprints
              </span>
            </h1>

            <p className="text-zinc-400 text-sm sm:text-base leading-relaxed mb-8">
              Production-grade systems reverse-engineered from active engineering
              requirements in Thailand. Every specification addresses real-world
              concurrency race conditions, distributed locking, and financial
              reconciliation standards.
            </p>

            {/* Architectural Quality Standards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-4 border-t border-white/[0.06] text-xs font-mono text-zinc-400">
              <div className="flex items-center gap-2">
                <Cpu className="h-3.5 w-3.5 text-cyan-400" />
                <span>P95 Stack Demand</span>
              </div>
              <div className="flex items-center gap-2">
                <Database className="h-3.5 w-3.5 text-sky-400" />
                <span>Zero Toy Projects</span>
              </div>
              <div className="flex items-center gap-2 col-span-2 sm:col-span-1">
                <Activity className="h-3.5 w-3.5 text-indigo-400" />
                <span>Interview Proof Specs</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Catalog Main */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex-1 w-full">
        <BlueprintCatalog initialProjects={projects} />
      </main>
    </div>
  );
}

import { getAllProjects } from "@/lib/turso";
import BlueprintCatalog from "@/components/BlueprintCatalog";
import ThreeCanvas from "@/components/ThreeCanvas";

export const revalidate = 60;

export default async function HomePage() {
  const projects = await getAllProjects();

  return (
    <div className="flex-1 flex flex-col relative">
      {/* Hero Section with Ambient Constrained Three.js Canvas */}
      <section className="relative overflow-hidden border-b border-white/[0.07] bg-gradient-to-b from-[#08080a] via-[#0d0e12]/50 to-[#08080a] py-16 sm:py-20">
        <ThreeCanvas />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="max-w-3xl">
            {/* Telemetry Ingestion Badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-950/60 border border-cyan-500/30 text-cyan-300 text-[11px] font-mono tracking-wide mb-6 shadow-sm">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping motion-reduce:hidden absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan-400" />
              </span>
              <span>TECH INGESTION ENGINE</span>
            </div>

            {/* Hero Heading */}
            <h1 className="text-3xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white mb-5 leading-[1.1]">
              Portfolio{" "}
              <span className="bg-gradient-to-r from-cyan-400 via-sky-300 to-indigo-400 bg-clip-text text-transparent">
                Architecture Blueprints
              </span>
            </h1>

            {/* Authoritative Microcopy */}
            <p className="text-zinc-400 text-sm sm:text-base leading-relaxed mb-8 max-w-2xl">
              Production-grade systems reverse-engineered from active engineering
              requirements in Thailand. Every specification addresses real-world
              concurrency race conditions, distributed locking, and financial
              reconciliation standards.
            </p>
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

import nextDynamic from "next/dynamic";
import { getMarketAnalytics } from "@/lib/turso";
import AnalyticsSkeleton from "@/components/AnalyticsSkeleton";
import SpotlightCard from "@/components/SpotlightCard";
import { Activity, Cpu, Layers, Sparkles } from "lucide-react";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

const AnalyticsCharts = nextDynamic(
  () => import("@/components/AnalyticsCharts"),
  {
    loading: () => <AnalyticsSkeleton />,
  }
);


export default async function AnalyticsPage() {
  const analytics = await getMarketAnalytics();

  if (!analytics) {
    return (
      <main className="max-w-7xl mx-auto px-4 py-16 text-sm text-zinc-400">
        No extracted job data yet. This page fills in after the daily pipeline completes its first extraction run.
      </main>
    );
  }

  const metrics = [
    {
      label: "Analyzed Postings",
      value: analytics.totalJobs.toLocaleString(),
      subtext: "Live Thailand scrapers",
      icon: Layers,
      color: "text-cyan-400",
    },
    {
      label: "Skill Clusters Extracted",
      value: analytics.totalSkills.toLocaleString(),
      subtext: "Normalized competencies",
      icon: Cpu,
      color: "text-sky-400",
    },
    {
      label: "Dominant Cloud Tier",
      value: analytics.clouds[0]?.name ?? "None yet",
      subtext: analytics.clouds[0] ? `${analytics.clouds[0].percentage}% of postings` : "",
      icon: Activity,
      color: "text-indigo-400",
    },
    {
      label: "Generated Blueprints",
      value: analytics.totalBlueprints.toLocaleString(),
      subtext: "Production specs ready",
      icon: Sparkles,
      color: "text-emerald-400",
    },
  ];

  return (
    <div className="flex-1 flex flex-col">
      {/* Header Section */}
      <section className="relative overflow-hidden border-b border-white/[0.07] bg-gradient-to-b from-[#08080a] via-[#0d0e12]/50 to-[#08080a] py-12 sm:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-950/60 border border-cyan-500/30 text-cyan-300 text-[11px] font-mono tracking-wide mb-4 shadow-sm">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping motion-reduce:hidden absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan-400" />
              </span>
              <span>CONTINUOUS INGESTION METRICS</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white mb-4">
              Market Intelligence &{" "}
              <span className="bg-gradient-to-r from-cyan-400 via-sky-300 to-indigo-400 bg-clip-text text-transparent">
                Tech Cluster Index
              </span>
            </h1>

            <p className="text-zinc-400 text-sm sm:text-base leading-relaxed">
              Empirical frequency distributions extracted from active software engineering
              job descriptions across Bangkok and Thailand. Zero speculative hype, only
              verifiable tech stack requirements.
            </p>
          </div>
        </div>
      </section>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex-1 w-full space-y-10">
        {/* Metric HUD Spotlight Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {metrics.map((m) => {
            const Icon = m.icon;
            return (
              <SpotlightCard
                key={m.label}
                className="p-5 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between text-zinc-500 mb-3">
                    <span className="text-xs font-mono">{m.label}</span>
                    <Icon className={`h-4 w-4 ${m.color}`} />
                  </div>
                  <div className="text-2xl sm:text-3xl font-bold font-mono text-white tracking-tight">
                    {m.value}
                  </div>
                  <div className="text-[11px] text-zinc-500 mt-1 font-mono">
                    {m.subtext}
                  </div>
                </div>
              </SpotlightCard>
            );
          })}
        </div>

        {/* Charts Section */}
        <AnalyticsCharts analytics={analytics} />
      </main>
    </div>
  );
}

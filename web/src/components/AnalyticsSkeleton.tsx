export default function AnalyticsSkeleton() {
  return (
    <div className="space-y-8" aria-busy="true" aria-label="Loading analytics charts">
      {/* 2-Column Analytics Charts Skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Skeleton 1: Bar Chart */}
        <div className="border border-white/[0.06] bg-zinc-950/40 rounded-xl animate-pulse min-h-[360px] p-6 flex flex-col justify-between">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
            <div className="flex items-center gap-2.5">
              <div className="h-4 w-4 rounded bg-cyan-500/20" />
              <div className="h-4 w-44 rounded bg-zinc-800/70" />
            </div>
            <div className="h-3 w-20 rounded bg-zinc-900" />
          </div>

          <div className="h-64 w-full flex flex-col justify-around py-4">
            {[85, 70, 58, 42, 35, 25].map((width, idx) => (
              <div key={idx} className="flex items-center gap-4">
                <div className="h-3 w-16 rounded bg-zinc-800/60" />
                <div
                  className="h-4 rounded bg-gradient-to-r from-cyan-500/15 to-sky-500/10"
                  style={{ width: `${width}%` }}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Skeleton 2: Pie / Donut Chart */}
        <div className="border border-white/[0.06] bg-zinc-950/40 rounded-xl animate-pulse min-h-[360px] p-6 flex flex-col justify-between">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
            <div className="flex items-center gap-2.5">
              <div className="h-4 w-4 rounded bg-indigo-500/20" />
              <div className="h-4 w-52 rounded bg-zinc-800/70" />
            </div>
            <div className="h-3 w-24 rounded bg-zinc-900" />
          </div>

          <div className="h-64 w-full flex items-center justify-center">
            <div className="h-44 w-44 rounded-full border-[18px] border-zinc-800/40 border-t-indigo-500/20 border-r-cyan-500/20" />
          </div>

          <div className="flex flex-wrap items-center justify-center gap-4 pt-3 border-t border-white/[0.04]">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-zinc-800" />
                <div className="h-3 w-16 rounded bg-zinc-900" />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Top Compensated Skills Skeleton */}
      <div className="border border-white/[0.06] bg-zinc-950/40 rounded-xl animate-pulse min-h-[300px] p-6 flex flex-col justify-between">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
          <div className="flex items-center gap-2.5">
            <div className="h-4 w-4 rounded bg-cyan-500/20" />
            <div className="h-4 w-60 rounded bg-zinc-800/70" />
          </div>
          <div className="h-3 w-28 rounded bg-zinc-900" />
        </div>
        <div className="h-48 w-full flex flex-col justify-around py-2">
          {[90, 75, 65, 50, 40].map((width, idx) => (
            <div key={idx} className="flex items-center gap-4">
              <div className="h-3 w-20 rounded bg-zinc-800/60" />
              <div
                className="h-3.5 rounded bg-gradient-to-r from-cyan-500/20 to-blue-500/10"
                style={{ width: `${width}%` }}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Database & Framework Grid Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Persistence & Data Engines Skeleton */}
        <div className="border border-white/[0.06] bg-zinc-950/40 rounded-xl animate-pulse p-6 space-y-4 min-h-[260px]">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded bg-sky-500/20" />
              <div className="h-3 w-48 rounded bg-zinc-800/70" />
            </div>
            <div className="h-2.5 w-20 rounded bg-zinc-900" />
          </div>
          <div className="space-y-4 pt-1">
            {[75, 60, 45, 30].map((width, idx) => (
              <div key={idx} className="space-y-2">
                <div className="flex justify-between">
                  <div className="h-3 w-20 rounded bg-zinc-800/60" />
                  <div className="h-3 w-8 rounded bg-zinc-800/60" />
                </div>
                <div className="h-1.5 w-full rounded-full bg-zinc-900">
                  <div
                    className="h-full rounded-full bg-cyan-500/20"
                    style={{ width: `${width}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Application Frameworks Skeleton */}
        <div className="border border-white/[0.06] bg-zinc-950/40 rounded-xl animate-pulse p-6 space-y-4 min-h-[260px]">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded bg-emerald-500/20" />
              <div className="h-3 w-44 rounded bg-zinc-800/70" />
            </div>
            <div className="h-2.5 w-20 rounded bg-zinc-900" />
          </div>
          <div className="space-y-4 pt-1">
            {[80, 55, 40, 25].map((width, idx) => (
              <div key={idx} className="space-y-2">
                <div className="flex justify-between">
                  <div className="h-3 w-20 rounded bg-zinc-800/60" />
                  <div className="h-3 w-8 rounded bg-zinc-800/60" />
                </div>
                <div className="h-1.5 w-full rounded-full bg-zinc-900">
                  <div
                    className="h-full rounded-full bg-emerald-500/20"
                    style={{ width: `${width}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function SkillGapSkeleton() {
  return (
    <div
      className="border border-white/[0.08] bg-zinc-950/60 rounded-2xl animate-pulse p-6 sm:p-8 min-h-[460px] flex flex-col justify-between"
      aria-busy="true"
      aria-label="Loading skill gap matcher"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-white/[0.06]">
        <div className="space-y-2">
          <div className="h-4 w-48 rounded bg-cyan-500/20" />
          <div className="h-6 w-72 rounded bg-zinc-800/80" />
          <div className="h-3 w-96 rounded bg-zinc-900" />
        </div>
        <div className="h-7 w-24 rounded bg-zinc-900" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 py-6">
        <div className="lg:col-span-7 space-y-4">
          <div className="h-3 w-40 rounded bg-zinc-800/60" />
          <div className="h-10 w-full rounded-xl bg-zinc-900/80" />
          <div className="flex gap-2">
            {[24, 20, 28].map((w, i) => (
              <div
                key={i}
                className="h-7 rounded-lg bg-cyan-950/40"
                style={{ width: `${w * 4}px` }}
              />
            ))}
          </div>
        </div>

        <div className="lg:col-span-5 bg-zinc-900/40 border border-white/[0.06] rounded-xl p-5 flex items-center gap-6">
          <div className="h-24 w-24 rounded-full border-8 border-zinc-800 shrink-0" />
          <div className="space-y-2 w-full">
            <div className="h-6 w-32 rounded bg-zinc-800/80" />
            <div className="h-3 w-44 rounded bg-zinc-800/50" />
            <div className="h-3 w-full rounded bg-zinc-900" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-6 border-t border-white/[0.06]">
        <div className="h-28 rounded-xl bg-zinc-900/50" />
        <div className="h-28 rounded-xl bg-zinc-900/50" />
      </div>
    </div>
  );
}

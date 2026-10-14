"use client";

import { useState, useRef, useMemo } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  PieChart,
  Pie,
} from "recharts";
import type { MarketAnalytics, MarketMetricItem } from "@/lib/turso";
import {
  Terminal,
  Cloud,
  Database,
  Code2,
  Banknote,
  Layers,
  Check,
  FileSpreadsheet,
  FileJson,
} from "lucide-react";
import SpotlightCard from "@/components/SpotlightCard";
import { cn } from "@/lib/utils";

interface AnalyticsChartsProps {
  analytics: MarketAnalytics;
}

type AnalyticsCategory =
  | "all"
  | "languages"
  | "cloud"
  | "compensation"
  | "frameworks";

interface CategoryTabConfig {
  id: AnalyticsCategory;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  count?: number;
}

const CLOUD_PALETTE = [
  "#06b6d4", // Cyan
  "#6366f1", // Indigo
  "#38bdf8", // Sky
  "#10b981", // Emerald
  "#a855f7", // Purple
  "#64748b", // Slate
];

interface TooltipPayloadItem {
  name: string;
  value: number;
  payload: MarketMetricItem;
}

interface SalaryTooltipPayloadItem {
  name: string;
  value: number;
  payload: {
    skill: string;
    avg_salary: number;
    sample_count: number;
  };
}

function CustomSalaryTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: SalaryTooltipPayloadItem[];
}) {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="rounded-lg bg-[#0c0d12] border border-white/10 px-3.5 py-2.5 text-xs shadow-2xl">
        <div className="font-semibold text-zinc-100">{data.skill}</div>
        <div className="font-mono tabular-nums text-cyan-300 font-semibold mt-1 flex items-center gap-1.5">
          <span>฿{data.avg_salary.toLocaleString()}/mo</span>
          <span className="text-zinc-500 font-normal text-[11px]">
            (n={data.sample_count} {data.sample_count === 1 ? "job" : "jobs"})
          </span>
        </div>
      </div>
    );
  }
  return null;
}

function CustomBarTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}) {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="rounded-lg bg-[#0c0d12] border border-white/10 px-3.5 py-2.5 text-xs shadow-2xl">
        <div className="font-semibold text-zinc-100">{data.name}</div>
        <div className="font-mono tabular-nums text-cyan-300 mt-1 flex items-center gap-1.5">
          <span className="font-semibold">{data.count} mentions</span>
          {data.percentage ? (
            <span className="text-zinc-500 font-normal">({data.percentage}% demand)</span>
          ) : null}
        </div>
      </div>
    );
  }
  return null;
}

function CustomPieTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}) {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="rounded-lg bg-[#0c0d12] border border-white/10 px-3.5 py-2.5 text-xs shadow-2xl">
        <div className="font-semibold text-zinc-100">{data.name}</div>
        <div className="font-mono tabular-nums text-indigo-300 mt-1">
          <span className="font-semibold">{data.count} positions</span> ({data.percentage ?? 0}%)
        </div>
      </div>
    );
  }
  return null;
}

function downloadBlob(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function escapeCsv(val: string | number | undefined | null): string {
  if (val === undefined || val === null) return '""';
  const str = String(val);
  return `"${str.replace(/"/g, '""')}"`;
}

function LanguagesCard({
  data,
  isExpanded,
}: {
  data: MarketMetricItem[];
  isExpanded?: boolean;
}) {
  return (
    <SpotlightCard className="p-6">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <Code2 className="h-4 w-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-white tracking-tight">
            Language Demand Index
          </h3>
        </div>
        <span className="text-[10px] font-mono text-zinc-500 uppercase">
          Frequency Rank
        </span>
      </div>

      <div className={cn("w-full", isExpanded ? "h-80 sm:h-96" : "h-64")}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 5, right: 20, left: 20, bottom: 5 }}
          >
            <XAxis
              type="number"
              stroke="#52525b"
              fontSize={11}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              dataKey="name"
              type="category"
              stroke="#a1a1aa"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              width={80}
            />
            <Tooltip
              content={<CustomBarTooltip />}
              cursor={{ fill: "rgba(255,255,255,0.03)" }}
            />
            <Bar dataKey="count" radius={[0, 4, 4, 0]}>
              {data.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={
                    index === 0
                      ? "#06b6d4"
                      : index === 1
                      ? "#38bdf8"
                      : "#0284c7"
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </SpotlightCard>
  );
}

function CloudCard({
  data,
  isExpanded,
}: {
  data: MarketMetricItem[];
  isExpanded?: boolean;
}) {
  return (
    <SpotlightCard className="p-6">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <Cloud className="h-4 w-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-white tracking-tight">
            Cloud & Containerization Share
          </h3>
        </div>
        <span className="text-[10px] font-mono text-zinc-500 uppercase">
          Production Stack
        </span>
      </div>

      <div
        className={cn(
          "w-full flex items-center justify-center",
          isExpanded ? "h-72 sm:h-80" : "h-64"
        )}
      >
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="count"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={isExpanded ? 65 : 55}
              outerRadius={isExpanded ? 105 : 85}
              paddingAngle={3}
            >
              {data.map((_, index) => (
                <Cell
                  key={`cloud-cell-${index}`}
                  fill={CLOUD_PALETTE[index % CLOUD_PALETTE.length]}
                />
              ))}
            </Pie>
            <Tooltip content={<CustomPieTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Minimalist Legend */}
      <div
        className={cn(
          "flex flex-wrap items-center justify-center gap-3 pt-3 border-t border-white/[0.04]",
          isExpanded && "grid grid-cols-2 sm:grid-cols-3 max-w-xl mx-auto"
        )}
      >
        {data.map((item, idx) => (
          <div
            key={item.name}
            className="flex items-center gap-1.5 text-xs font-mono"
          >
            <span
              className="h-2 w-2 rounded-full shrink-0"
              style={{
                backgroundColor: CLOUD_PALETTE[idx % CLOUD_PALETTE.length],
              }}
            />
            <span className="text-zinc-400">{item.name}</span>
            <span className="text-zinc-500 font-sans text-[11px]">
              ({item.percentage}%)
            </span>
          </div>
        ))}
      </div>
    </SpotlightCard>
  );
}

function CompensationCard({
  topCompensatedSkills,
}: {
  topCompensatedSkills?: MarketAnalytics["top_compensated_skills"];
}) {
  return (
    <SpotlightCard className="p-6">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <Banknote className="h-4 w-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-white tracking-tight">
            Top Compensated Skills (THB/month, n ≥ 5)
          </h3>
        </div>
        <span className="text-[10px] font-mono text-zinc-500 uppercase">
          Sample size: n ≥ 5 postings
        </span>
      </div>

      {topCompensatedSkills && topCompensatedSkills.length > 0 ? (
        <div className="space-y-4">
          <div className="h-64 sm:h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={topCompensatedSkills}
                layout="vertical"
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
              >
                <XAxis
                  type="number"
                  stroke="#52525b"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) => `฿${(v / 1000).toFixed(0)}k`}
                />
                <YAxis
                  dataKey="skill"
                  type="category"
                  stroke="#a1a1aa"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  width={90}
                />
                <Tooltip
                  content={<CustomSalaryTooltip />}
                  cursor={{ fill: "rgba(255,255,255,0.03)" }}
                />
                <Bar dataKey="avg_salary" radius={[0, 4, 4, 0]}>
                  {topCompensatedSkills.map((_, index) => (
                    <Cell
                      key={`cell-salary-${index}`}
                      fill={
                        index === 0
                          ? "#06b6d4"
                          : index === 1
                          ? "#38bdf8"
                          : "#3b82f6"
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Tabular Compensation Benchmark Table */}
          <div className="pt-4 border-t border-white/[0.06] overflow-x-auto">
            <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 mb-2 flex items-center justify-between">
              <span>Benchmark Breakdown</span>
              <span>Verified Postings</span>
            </div>
            <div className="divide-y divide-white/[0.04] text-xs font-mono">
              <div className="grid grid-cols-12 pb-2 text-zinc-500 font-medium">
                <div className="col-span-6 sm:col-span-5 text-left">Skill / Competency</div>
                <div className="col-span-4 sm:col-span-4 text-right">Average Monthly</div>
                <div className="col-span-2 sm:col-span-3 text-right">Sample (n)</div>
              </div>
              {topCompensatedSkills.map((item) => (
                <div
                  key={item.skill}
                  className="grid grid-cols-12 py-2 items-center hover:bg-white/[0.02] transition-colors"
                >
                  <div className="col-span-6 sm:col-span-5 text-left font-medium text-zinc-200">
                    {item.skill}
                  </div>
                  <div className="col-span-4 sm:col-span-4 text-right font-mono tabular-nums text-cyan-300 font-semibold">
                    ฿{item.avg_salary.toLocaleString()}/mo
                  </div>
                  <div className="col-span-2 sm:col-span-3 text-right font-mono tabular-nums text-zinc-500 text-[11px]">
                    n={item.sample_count}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="h-48 flex flex-col items-center justify-center text-center p-6 border border-dashed border-white/[0.08] rounded-xl bg-zinc-950/20">
          <Banknote className="h-8 w-8 text-zinc-600 mb-2.5 stroke-1" />
          <p className="text-xs font-mono text-zinc-400 max-w-md">
            Insufficient salary data disclosed across current postings. As additional postings with compensation details are ingested, compensation benchmarks will automatically populate here.
          </p>
        </div>
      )}
    </SpotlightCard>
  );
}

function DatabasesCard({ data }: { data: MarketMetricItem[] }) {
  return (
    <SpotlightCard className="p-6">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-sky-400" />
          <h4 className="text-xs font-semibold text-white uppercase tracking-wider font-mono">
            Persistence & Storage Engines
          </h4>
        </div>
        <span className="text-[10px] font-mono text-zinc-500">Frequency Rank</span>
      </div>
      <div className="space-y-3.5">
        {data.map((db) => (
          <div key={db.name} className="space-y-1.5">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-zinc-300 font-medium">{db.name}</span>
              <span className="text-cyan-400 tabular-nums">{db.percentage ?? 0}%</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-zinc-800/80 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-sky-400"
                style={{ width: `${Math.min(db.percentage ?? 0, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </SpotlightCard>
  );
}

function FrameworksCard({ data }: { data: MarketMetricItem[] }) {
  return (
    <SpotlightCard className="p-6">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-emerald-400" />
          <h4 className="text-xs font-semibold text-white uppercase tracking-wider font-mono">
            Application Frameworks
          </h4>
        </div>
        <span className="text-[10px] font-mono text-zinc-500">Frequency Rank</span>
      </div>
      <div className="space-y-3.5">
        {data.map((fw) => (
          <div key={fw.name} className="space-y-1.5">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-zinc-300 font-medium">{fw.name}</span>
              <span className="text-emerald-400 tabular-nums">{fw.percentage ?? 0}%</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-zinc-800/80 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400"
                style={{ width: `${Math.min(fw.percentage ?? 0, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </SpotlightCard>
  );
}

export default function AnalyticsCharts({ analytics }: AnalyticsChartsProps) {
  const [activeCategory, setActiveCategory] = useState<AnalyticsCategory>("all");
  const [exportStatus, setExportStatus] = useState<"idle" | "csv" | "json">("idle");
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const categories: CategoryTabConfig[] = useMemo(
    () => [
      {
        id: "all",
        label: "All Metrics",
        icon: Layers,
        count:
          analytics.languages.length +
          analytics.clouds.length +
          (analytics.top_compensated_skills?.length ?? 0) +
          analytics.databases.length +
          analytics.frameworks.length,
      },
      {
        id: "languages",
        label: "Languages",
        icon: Code2,
        count: analytics.languages.length,
      },
      {
        id: "cloud",
        label: "Cloud & Infra",
        icon: Cloud,
        count: analytics.clouds.length,
      },
      {
        id: "compensation",
        label: "Compensation",
        icon: Banknote,
        count: analytics.top_compensated_skills?.length ?? 0,
      },
      {
        id: "frameworks",
        label: "Data & Frameworks",
        icon: Database,
        count: analytics.databases.length + analytics.frameworks.length,
      },
    ],
    [analytics]
  );

  const activeCategoryLabel =
    categories.find((c) => c.id === activeCategory)?.label ?? "All Metrics";

  const handleTabKeyDown = (e: React.KeyboardEvent, index: number) => {
    const tabCount = categories.length;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      const nextIdx = (index + 1) % tabCount;
      setActiveCategory(categories[nextIdx].id);
      tabRefs.current[nextIdx]?.focus();
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      const prevIdx = (index - 1 + tabCount) % tabCount;
      setActiveCategory(categories[prevIdx].id);
      tabRefs.current[prevIdx]?.focus();
    } else if (e.key === "Home") {
      e.preventDefault();
      setActiveCategory(categories[0].id);
      tabRefs.current[0]?.focus();
    } else if (e.key === "End") {
      e.preventDefault();
      setActiveCategory(categories[tabCount - 1].id);
      tabRefs.current[tabCount - 1]?.focus();
    }
  };

  const exportCSV = () => {
    const today = new Date().toISOString().split("T")[0];
    const filename = `jhunt-market-analytics-${today}.csv`;
    const rows: string[] = [
      "Category,Skill_Name,Demand_Count,Demand_Percentage,Avg_Salary_THB,Sample_Count",
    ];

    analytics.languages.forEach((item) => {
      rows.push(
        `"Language",${escapeCsv(item.name)},${item.count},${item.percentage ?? ""},"",""`
      );
    });

    analytics.clouds.forEach((item) => {
      rows.push(
        `"Cloud & Infra",${escapeCsv(item.name)},${item.count},${item.percentage ?? ""},"",""`
      );
    });

    analytics.databases.forEach((item) => {
      rows.push(
        `"Database",${escapeCsv(item.name)},${item.count},${item.percentage ?? ""},"",""`
      );
    });

    analytics.frameworks.forEach((item) => {
      rows.push(
        `"Framework",${escapeCsv(item.name)},${item.count},${item.percentage ?? ""},"",""`
      );
    });

    (analytics.top_compensated_skills || []).forEach((item) => {
      rows.push(
        `"Compensation",${escapeCsv(item.skill)},"","",${item.avg_salary},${item.sample_count}`
      );
    });

    const csvContent = "\uFEFF" + rows.join("\r\n");
    downloadBlob(csvContent, filename, "text/csv;charset=utf-8;");
    setExportStatus("csv");
    setTimeout(() => setExportStatus("idle"), 2000);
  };

  const exportJSON = () => {
    const today = new Date().toISOString().split("T")[0];
    const filename = `jhunt-market-analytics-${today}.json`;
    const payload = {
      metadata: {
        source: "JHunt Thailand Tech Market Telemetry",
        exported_at: new Date().toISOString(),
        total_jobs: analytics.totalJobs,
        total_skills: analytics.totalSkills,
        total_blueprints: analytics.totalBlueprints,
      },
      languages: analytics.languages,
      clouds: analytics.clouds,
      top_compensated_skills: analytics.top_compensated_skills || [],
      databases: analytics.databases,
      frameworks: analytics.frameworks,
    };
    downloadBlob(
      JSON.stringify(payload, null, 2),
      filename,
      "application/json;charset=utf-8;"
    );
    setExportStatus("json");
    setTimeout(() => setExportStatus("idle"), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Interactive Category Filter & Export Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 p-2 sm:p-2.5 rounded-2xl bg-zinc-950/70 border border-white/[0.08] backdrop-blur-xl">
        {/* WAI-ARIA Category Filter Tabs */}
        <div
          role="tablist"
          aria-label="Market analytics category filters"
          className="flex items-center gap-1.5 overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden py-0.5"
        >
          {categories.map((cat, idx) => {
            const isSelected = activeCategory === cat.id;
            const Icon = cat.icon;
            return (
              <button
                key={cat.id}
                ref={(el) => {
                  tabRefs.current[idx] = el;
                }}
                role="tab"
                id={`tab-${cat.id}`}
                aria-selected={isSelected}
                aria-controls={`panel-${cat.id}`}
                tabIndex={isSelected ? 0 : -1}
                onClick={() => setActiveCategory(cat.id)}
                onKeyDown={(e) => handleTabKeyDown(e, idx)}
                className={cn(
                  "inline-flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-mono font-medium transition-all duration-150 shrink-0 min-h-[44px] active:scale-95",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950",
                  isSelected
                    ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/40 ring-1 ring-cyan-500/30 shadow-sm"
                    : "bg-zinc-900/80 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/80 border border-white/[0.08]"
                )}
              >
                <Icon
                  className={cn(
                    "h-3.5 w-3.5",
                    isSelected ? "text-cyan-400" : "text-zinc-500"
                  )}
                />
                <span>{cat.label}</span>
                {cat.count !== undefined && (
                  <span
                    className={cn(
                      "text-[10px] px-1.5 py-0.5 rounded-full font-mono tabular-nums",
                      isSelected
                        ? "bg-cyan-950 text-cyan-300 border border-cyan-500/30"
                        : "bg-zinc-800 text-zinc-500"
                    )}
                  >
                    {cat.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Data Export Action Group */}
        <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
          <button
            onClick={exportCSV}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-mono font-medium bg-zinc-900 text-zinc-300 hover:text-white hover:bg-zinc-800/80 border border-white/10 hover:border-cyan-500/40 active:scale-95 transition-all duration-150 min-h-[44px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
            title="Download CSV spreadsheet"
            aria-label="Export market analytics as CSV"
          >
            {exportStatus === "csv" ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-emerald-400">Exported!</span>
              </>
            ) : (
              <>
                <FileSpreadsheet className="h-3.5 w-3.5 text-cyan-400" />
                <span>Export CSV</span>
              </>
            )}
          </button>

          <button
            onClick={exportJSON}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-mono font-medium bg-zinc-900 text-zinc-300 hover:text-white hover:bg-zinc-800/80 border border-white/10 hover:border-cyan-500/40 active:scale-95 transition-all duration-150 min-h-[44px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
            title="Download JSON telemetry"
            aria-label="Export market analytics as JSON"
          >
            {exportStatus === "json" ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-emerald-400">Exported!</span>
              </>
            ) : (
              <>
                <FileJson className="h-3.5 w-3.5 text-indigo-400" />
                <span>Export JSON</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Screen Reader Live Region for Filter & Export State */}
      <div className="sr-only" aria-live="polite">
        {exportStatus === "csv"
          ? "Market analytics exported as CSV spreadsheet"
          : exportStatus === "json"
          ? "Market analytics exported as JSON dataset"
          : `Viewing ${activeCategoryLabel} telemetry`}
      </div>

      {/* Dynamic Tabpanel Rendering */}
      <div
        role="tabpanel"
        id={`panel-${activeCategory}`}
        aria-labelledby={`tab-${activeCategory}`}
        className="focus:outline-none"
      >
        {activeCategory === "all" && (
          <div className="space-y-8">
            {/* 2-Column Languages & Cloud Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <LanguagesCard data={analytics.languages} />
              <CloudCard data={analytics.clouds} />
            </div>

            {/* Compensation Benchmarks */}
            <CompensationCard
              topCompensatedSkills={analytics.top_compensated_skills}
            />

            {/* Databases & Frameworks Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <DatabasesCard data={analytics.databases} />
              <FrameworksCard data={analytics.frameworks} />
            </div>
          </div>
        )}

        {activeCategory === "languages" && (
          <LanguagesCard data={analytics.languages} isExpanded />
        )}

        {activeCategory === "cloud" && (
          <CloudCard data={analytics.clouds} isExpanded />
        )}

        {activeCategory === "compensation" && (
          <CompensationCard
            topCompensatedSkills={analytics.top_compensated_skills}
          />
        )}

        {activeCategory === "frameworks" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <DatabasesCard data={analytics.databases} />
            <FrameworksCard data={analytics.frameworks} />
          </div>
        )}
      </div>
    </div>
  );
}

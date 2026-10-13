"use client";

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
import { Terminal, Cloud, Database, Code2, Banknote } from "lucide-react";
import SpotlightCard from "@/components/SpotlightCard";

interface AnalyticsChartsProps {
  analytics: MarketAnalytics;
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
        <div className="font-mono text-cyan-400 mt-1 flex items-center gap-1.5">
          <span>฿{data.avg_salary.toLocaleString()}/mo</span>
          <span className="text-zinc-500">
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
        <div className="font-mono text-cyan-400 mt-1 flex items-center gap-1.5">
          <span>{data.count} mentions</span>
          {data.percentage ? (
            <span className="text-zinc-500">({data.percentage}% demand)</span>
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
        <div className="font-mono text-indigo-400 mt-1">
          {data.count} positions ({data.percentage ?? 0}%)
        </div>
      </div>
    );
  }
  return null;
}

export default function AnalyticsCharts({ analytics }: AnalyticsChartsProps) {
  return (
    <div className="space-y-8">
      {/* 2-Column Analytics Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart 1: Language Demand Index */}
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

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={analytics.languages}
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
                  {analytics.languages.map((_, index) => (
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

        {/* Chart 2: Cloud Infrastructure Share */}
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

          <div className="h-64 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={analytics.clouds}
                  dataKey="count"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={3}
                >
                  {analytics.clouds.map((_, index) => (
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
          <div className="flex flex-wrap items-center justify-center gap-3 pt-3 border-t border-white/[0.04]">
            {analytics.clouds.map((item, idx) => (
              <div
                key={item.name}
                className="flex items-center gap-1.5 text-xs font-mono"
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{
                    backgroundColor:
                      CLOUD_PALETTE[idx % CLOUD_PALETTE.length],
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
      </div>

      {/* Chart 3: Top Compensated Tech Skills */}
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

        {analytics.top_compensated_skills && analytics.top_compensated_skills.length > 0 ? (
          <div className="space-y-4">
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={analytics.top_compensated_skills}
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
                    {analytics.top_compensated_skills.map((_, index) => (
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

            {/* Quick Benchmark Pills */}
            <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-white/[0.04]">
              {analytics.top_compensated_skills.slice(0, 6).map((item) => (
                <div
                  key={item.skill}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-900 border border-white/[0.06] text-xs font-mono"
                >
                  <span className="text-zinc-300">{item.skill}:</span>
                  <span className="text-cyan-400 font-semibold">
                    ฿{item.avg_salary.toLocaleString()}/mo
                  </span>
                  <span className="text-zinc-500 text-[11px]">
                    (n={item.sample_count} {item.sample_count === 1 ? "job" : "jobs"})
                  </span>
                </div>
              ))}
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

      {/* Database & Framework Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Persistence & Data Engines */}
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
            {analytics.databases.map((db) => (
              <div key={db.name} className="space-y-1.5">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-zinc-300 font-medium">{db.name}</span>
                  <span className="text-cyan-400">{db.percentage ?? 0}%</span>
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

        {/* Application Frameworks */}
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
            {analytics.frameworks.map((fw) => (
              <div key={fw.name} className="space-y-1.5">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-zinc-300 font-medium">{fw.name}</span>
                  <span className="text-emerald-400">{fw.percentage ?? 0}%</span>
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
      </div>
    </div>
  );
}

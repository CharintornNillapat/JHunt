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
import { Terminal, Cloud, Database, Code2 } from "lucide-react";

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
      <div className="rounded-lg bg-zinc-900/95 border border-white/10 px-3 py-2 text-xs shadow-xl backdrop-blur-md">
        <div className="font-semibold text-zinc-100">{data.name}</div>
        <div className="font-mono text-cyan-400 mt-0.5">
          {data.count} mentions{" "}
          {data.percentage ? `(${data.percentage}% demand)` : ""}
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
      <div className="rounded-lg bg-zinc-900/95 border border-white/10 px-3 py-2 text-xs shadow-xl backdrop-blur-md">
        <div className="font-semibold text-zinc-100">{data.name}</div>
        <div className="font-mono text-indigo-400 mt-0.5">
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
        <div className="rounded-xl border border-white/[0.08] bg-zinc-900/50 backdrop-blur-md p-6">
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
                <Tooltip content={<CustomBarTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {analytics.languages.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={index === 0 ? "#06b6d4" : index === 1 ? "#38bdf8" : "#0284c7"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Cloud Infrastructure Share */}
        <div className="rounded-xl border border-white/[0.08] bg-zinc-900/50 backdrop-blur-md p-6">
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
              <div key={item.name} className="flex items-center gap-1.5 text-xs font-mono">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: CLOUD_PALETTE[idx % CLOUD_PALETTE.length] }}
                />
                <span className="text-zinc-400">{item.name}</span>
                <span className="text-zinc-500 font-sans text-[11px]">
                  ({item.percentage}%)
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Database & Framework Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Persistence & Data Engines */}
        <div className="rounded-xl border border-white/[0.08] bg-zinc-900/50 backdrop-blur-md p-6">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-sky-400" />
              <h4 className="text-xs font-semibold text-white uppercase tracking-wider font-mono">
                Persistence & Storage Engines
              </h4>
            </div>
            <span className="text-[10px] font-mono text-zinc-500">Live P95</span>
          </div>
          <div className="space-y-3">
            {analytics.databases.map((db) => (
              <div key={db.name} className="space-y-1">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-zinc-300">{db.name}</span>
                  <span className="text-zinc-500">{db.percentage ?? 0}%</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-zinc-800/80 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-sky-500/80"
                    style={{ width: `${Math.min(db.percentage ?? 0, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Application Frameworks */}
        <div className="rounded-xl border border-white/[0.08] bg-zinc-900/50 backdrop-blur-md p-6">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-emerald-400" />
              <h4 className="text-xs font-semibold text-white uppercase tracking-wider font-mono">
                Application Frameworks
              </h4>
            </div>
            <span className="text-[10px] font-mono text-zinc-500">Live P95</span>
          </div>
          <div className="space-y-3">
            {analytics.frameworks.map((fw) => (
              <div key={fw.name} className="space-y-1">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-zinc-300">{fw.name}</span>
                  <span className="text-zinc-500">{fw.percentage ?? 0}%</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-zinc-800/80 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-emerald-500/80"
                    style={{ width: `${Math.min(fw.percentage ?? 0, 100)}%` }}
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

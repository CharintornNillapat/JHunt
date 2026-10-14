"use client";

import React, { useState, useEffect, useRef, useTransition } from "react";
import Link from "next/link";
import {
  Sparkles,
  Plus,
  X,
  TrendingUp,
  Check,
  CheckCircle2,
  Search,
  ArrowUpRight,
  Layers,
  Zap,
  Banknote,
} from "lucide-react";
import SpotlightCard from "./SpotlightCard";
import type { SkillGapResponse } from "@/lib/skill-gap-types";
import { cn } from "@/lib/utils";

interface SkillGapMatcherProps {
  initialData?: SkillGapResponse | null;
}

interface StackPreset {
  id: string;
  label: string;
  description: string;
  skills: string[];
}

const STACK_PRESETS: StackPreset[] = [
  {
    id: "fullstack-ts",
    label: "Full-Stack TS",
    description: "Modern TypeScript and React ecosystem",
    skills: ["TypeScript", "React", "Next.js", "Node.js", "PostgreSQL"],
  },
  {
    id: "python-backend",
    label: "Python Backend",
    description: "High-throughput asynchronous API services",
    skills: ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"],
  },
  {
    id: "data-ml",
    label: "Data & ML",
    description: "Data pipelines and distributed workloads",
    skills: ["Python", "PostgreSQL", "Docker", "AWS", "Kubernetes"],
  },
  {
    id: "cloud-systems",
    label: "Cloud Systems",
    description: "Microservices and infrastructure orchestration",
    skills: ["Go", "Docker", "Kubernetes", "PostgreSQL", "Redis"],
  },
];

function RadialGauge({
  percentage,
  isHighlight,
}: {
  percentage: number;
  isHighlight?: boolean;
}) {
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset =
    circumference - (Math.min(100, Math.max(0, percentage)) / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center shrink-0">
      <svg
        className="w-16 h-16 sm:w-24 sm:h-24 transform -rotate-90 transition-transform duration-500"
        viewBox="0 0 96 96"
      >
        <circle
          cx="48"
          cy="48"
          r={radius}
          className="text-zinc-800/80 stroke-current"
          strokeWidth="7"
          fill="transparent"
        />
        <circle
          cx="48"
          cy="48"
          r={radius}
          className={cn(
            "stroke-current transition-all duration-700 ease-out",
            isHighlight ? "text-emerald-400" : "text-cyan-400"
          )}
          strokeWidth="7"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          fill="transparent"
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center text-center">
        <span className="text-xl sm:text-2xl font-bold font-mono text-white tracking-tight tabular-nums">
          {percentage}%
        </span>
        <span className="text-[8px] sm:text-[9px] font-mono uppercase tracking-wider text-zinc-400">
          Reach
        </span>
      </div>
    </div>
  );
}

function areSkillSetsEqual(a?: string[], b?: string[]): boolean {
  if (!a && !b) return true;
  if (!a || !b) return false;
  if (a.length !== b.length) return false;
  const setA = new Set(a.map((s) => s.trim().toLowerCase()).filter(Boolean));
  const setB = new Set(b.map((s) => s.trim().toLowerCase()).filter(Boolean));
  if (setA.size !== setB.size) return false;
  for (const item of setA) {
    if (!setB.has(item)) return false;
  }
  return true;
}

export default function SkillGapMatcher({ initialData }: SkillGapMatcherProps) {
  const [selectedSkills, setSelectedSkills] = useState<string[]>(
    initialData?.userSkills && initialData.userSkills.length > 0
      ? initialData.userSkills
      : ["Python", "FastAPI"]
  );

  const [data, setData] = useState<SkillGapResponse | null>(initialData ?? null);
  const [inputValue, setInputValue] = useState("");
  const [, startTransition] = useTransition();
  const [isLoading, setIsLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const lastFetchedSkillsRef = useRef<string[] | null>(
    initialData?.userSkills ?? null
  );
  const prevCoverageRef = useRef<number>(initialData?.coverageRate ?? 0);
  const [delta, setDelta] = useState<number | null>(null);

  useEffect(() => {
    if (data?.coverageRate !== undefined && data.coverageRate !== prevCoverageRef.current) {
      const diff = data.coverageRate - prevCoverageRef.current;
      if (diff !== 0) {
        setDelta(diff);
        const timer = setTimeout(() => setDelta(null), 3500);
        prevCoverageRef.current = data.coverageRate;
        return () => clearTimeout(timer);
      }
    }
  }, [data?.coverageRate]);

  // Compute popular suggestions (from live data or baseline)
  const popularSkills =
    data?.popularSuggestions && data.popularSuggestions.length > 0
      ? data.popularSuggestions.slice(0, 12)
      : [
          "Python",
          "TypeScript",
          "React",
          "Docker",
          "PostgreSQL",
          "FastAPI",
          "AWS",
          "Go",
          "Kubernetes",
          "Next.js",
          "Redis",
          "Node.js",
        ];

  // Dynamic filter for input autocomplete
  const filteredSuggestions = inputValue.trim()
    ? popularSkills
        .filter(
          (s) =>
            s.toLowerCase().includes(inputValue.toLowerCase()) &&
            !selectedSkills.some((sel) => sel.toLowerCase() === s.toLowerCase())
        )
        .slice(0, 5)
    : [];

  // Fetch updated metrics when selectedSkills changes
  useEffect(() => {
    // Avoid re-fetching on initial mount if server already provided identical initialData
    if (areSkillSetsEqual(selectedSkills, lastFetchedSkillsRef.current ?? undefined)) {
      return;
    }

    let isCancelled = false;
    const controller = new AbortController();

    async function fetchGap() {
      setIsLoading(true);
      try {
        const res = await fetch("/api/skill-gap", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userSkills: selectedSkills }),
          signal: controller.signal,
        });
        if (!res.ok) throw new Error("Failed to calculate skill gap");
        const json: SkillGapResponse = await res.json();
        if (!isCancelled) {
          lastFetchedSkillsRef.current = selectedSkills;
          startTransition(() => {
            setData(json);
          });
        }
      } catch (err: unknown) {
        if ((err as Error).name !== "AbortError") {
          console.error("Skill gap matcher fetch error:", err);
        }
      } finally {
        if (!isCancelled) setIsLoading(false);
      }
    }

    fetchGap();

    return () => {
      isCancelled = true;
      controller.abort();
    };
  }, [selectedSkills]);

  const addSkill = (skill: string) => {
    const trimmed = skill.trim();
    if (!trimmed) return;
    if (selectedSkills.some((s) => s.toLowerCase() === trimmed.toLowerCase())) return;
    setSelectedSkills((prev) => [...prev, trimmed]);
    setInputValue("");
    if (inputRef.current) inputRef.current.focus();
  };

  const removeSkill = (skill: string) => {
    setSelectedSkills((prev) =>
      prev.filter((s) => s.toLowerCase() !== skill.toLowerCase())
    );
  };

  const clearAllSkills = () => {
    setSelectedSkills([]);
    setInputValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && inputValue.trim()) {
      e.preventDefault();
      addSkill(inputValue);
    }
  };

  const coverageRate = data?.coverageRate ?? 0;
  const matchedJobsCount = data?.matchedJobsCount ?? 0;
  const totalTechJobs = data?.totalTechJobs ?? 0;

  // Fit assessment label
  const fitAssessment =
    selectedSkills.length === 0
      ? { label: "Select competencies to benchmark", color: "text-zinc-500" }
      : coverageRate >= 50
      ? { label: "Dominant Market Fit (High Demand)", color: "text-emerald-400" }
      : coverageRate >= 25
      ? { label: "Solid Core Stack (Targeted Fit)", color: "text-cyan-400" }
      : { label: "Niche / Emerging Competency Profile", color: "text-amber-400" };

  return (
    <SpotlightCard
      className="p-4 sm:p-6 lg:p-8 border border-white/[0.08] bg-[#0c0d12] rounded-2xl relative overflow-hidden backdrop-blur-xl"
      spotlightColor="rgba(6, 182, 212, 0.15)"
    >
      {/* Background radial glow accents */}
      <div className="absolute top-0 right-0 -mr-24 -mt-24 w-80 h-80 rounded-full bg-cyan-500/[0.07] blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-0 -ml-24 -mb-24 w-80 h-80 rounded-full bg-indigo-500/[0.05] blur-3xl pointer-events-none" />

      {/* Screen Reader Live Region for Metric Updates (antislop R-32) */}
      <div className="sr-only" aria-live="polite">
        {`Market coverage updated to ${coverageRate}%${delta ? `, a ${delta}% increase` : ""}`}
      </div>

      {/* Widget Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-white/[0.06]">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-cyan-950/70 border border-cyan-500/30 text-cyan-300 text-[11px] font-mono tracking-wider uppercase mb-2.5">
            <Sparkles className="h-3 w-3 text-cyan-400" />
            <span>TALENT BENCHMARK & ROI ENGINE</span>
          </div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            Skill Gap Matcher
            <span className="text-xs font-mono font-normal text-zinc-500 px-2 py-0.5 rounded bg-zinc-900 border border-white/[0.06]">
              Live LibSQL Telemetry
            </span>
          </h2>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-2xl leading-relaxed">
            Benchmark your stack against real hiring requirements. Identify high-leverage
            synergies that unlock additional job postings and match architecture specs.
          </p>
        </div>

        {selectedSkills.length > 0 && (
          <button
            onClick={clearAllSkills}
            className="self-start sm:self-center text-xs font-mono text-zinc-400 hover:text-rose-400 transition-all duration-150 px-3 py-1.5 rounded-lg border border-white/[0.06] hover:border-rose-500/30 bg-zinc-900/40 min-h-[44px] flex items-center justify-center active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
          >
            Clear Stack
          </button>
        )}
      </div>

      {/* Main Interactive Benchmarking Area */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 py-6">
        {/* Left Column: Skill Tag Selector & Input (7 cols) */}
        <div className="lg:col-span-7 flex flex-col justify-between space-y-6">
          <div>
            {/* 1-Click Role Stack Presets */}
            <div className="mb-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
                  Role Stack Presets:
                </span>
                <span className="text-[10px] font-mono text-zinc-500">
                  Instant 1-Click Benchmark
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 sm:gap-2">
                {STACK_PRESETS.map((preset) => {
                  const isActive = areSkillSetsEqual(selectedSkills, preset.skills);
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => setSelectedSkills(preset.skills)}
                      aria-pressed={isActive}
                      title={preset.description}
                      className={cn(
                        "flex flex-col text-left p-2 sm:p-2.5 rounded-lg border transition-all duration-150 min-h-[44px] justify-center active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950",
                        isActive
                          ? "bg-cyan-950/90 border-cyan-500/50 text-cyan-200 ring-1 ring-cyan-500/30 shadow-sm"
                          : "bg-zinc-900/70 border-white/[0.08] text-zinc-300 hover:text-white hover:bg-zinc-800/80 hover:border-white/[0.15]"
                      )}
                    >
                      <span className="text-xs font-semibold font-mono leading-tight">
                        {preset.label}
                      </span>
                      <span className="text-[10px] text-zinc-400 font-mono truncate mt-0.5">
                        {preset.skills.slice(0, 3).join(", ")}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            <label className="block text-xs font-mono uppercase tracking-wider text-zinc-400 mb-2">
              Current Competency Stack ({selectedSkills.length} selected)
            </label>

            {/* Input Field with Autocomplete */}
            <div className="relative">
              <div className="relative flex items-center">
                <Search className="absolute left-3.5 h-4 w-4 text-zinc-500 pointer-events-none" />
                <input
                  ref={inputRef}
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type a skill (e.g. Docker, React, AWS) and press Enter..."
                  className="w-full pl-10 pr-12 py-2.5 text-sm bg-zinc-900/90 border border-white/[0.1] rounded-xl text-white placeholder-zinc-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 transition-all font-mono min-h-[44px]"
                />
                {inputValue && (
                  <button
                    onClick={() => addSkill(inputValue)}
                    className="absolute right-2 px-2.5 py-1 text-xs font-mono rounded bg-cyan-950 border border-cyan-500/40 text-cyan-300 hover:bg-cyan-900 active:scale-95 transition-all min-h-[32px] flex items-center justify-center"
                  >
                    Add
                  </button>
                )}
              </div>

              {/* Autocomplete Dropdown */}
              {filteredSuggestions.length > 0 && (
                <div className="absolute z-20 mt-1 w-full bg-zinc-900 border border-white/[0.1] rounded-lg shadow-2xl py-1 overflow-hidden">
                  {filteredSuggestions.map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => addSkill(suggestion)}
                      className="w-full text-left px-3.5 py-2.5 min-h-[44px] text-xs font-mono text-zinc-300 hover:bg-cyan-950/60 hover:text-cyan-300 active:scale-95 flex items-center justify-between transition-all duration-150"
                    >
                      <span>{suggestion}</span>
                      <Plus className="h-3.5 w-3.5 text-cyan-400" />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Active Selected Skill Chips */}
            <div className="flex flex-wrap items-center gap-2 mt-3 min-h-[38px]">
              {selectedSkills.length === 0 ? (
                <span className="text-xs font-mono text-zinc-500 italic">
                  No skills selected yet. Pick from the popular suggestions below or type above.
                </span>
              ) : (
                selectedSkills.map((skill) => (
                  <span
                    key={skill}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono bg-cyan-950/60 border border-cyan-500/30 text-cyan-200 shadow-sm transition-all"
                  >
                    <span>{skill}</span>
                    <button
                      onClick={() => removeSkill(skill)}
                      className="hover:text-white active:scale-90 transition-transform p-0.5 rounded-full hover:bg-cyan-900/60"
                      aria-label={`Remove ${skill}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))
              )}
            </div>
          </div>

          {/* Quick-Add Popular Skills Row */}
          <div>
            <span className="block text-[11px] font-mono text-zinc-500 uppercase tracking-wider mb-2">
              Quick Toggle Popular Skills:
            </span>
            <div className="flex flex-wrap gap-1.5">
              {popularSkills.map((skill) => {
                const isSelected = selectedSkills.some(
                  (s) => s.toLowerCase() === skill.toLowerCase()
                );
                return (
                  <button
                    key={skill}
                    onClick={() => (isSelected ? removeSkill(skill) : addSkill(skill))}
                    className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-mono transition-all duration-150 border min-h-[44px] active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-1 focus-visible:ring-offset-zinc-950 ${
                      isSelected
                        ? "bg-cyan-950/90 border-cyan-500/50 text-cyan-300 shadow-sm"
                        : "bg-zinc-900/60 border-white/[0.06] text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60 hover:border-white/[0.12]"
                    }`}
                  >
                    {isSelected ? (
                      <Check className="h-3 w-3 text-cyan-400" />
                    ) : (
                      <Plus className="h-3 w-3 text-zinc-500" />
                    )}
                    <span>{skill}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Live Market Coverage HUD Gauge (5 cols) */}
        <div className="lg:col-span-5 flex flex-col justify-between bg-zinc-900/30 border border-white/[0.05] rounded-xl p-4 sm:p-5 relative">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.05]">
            <span className="text-xs font-mono text-zinc-400 uppercase tracking-wider">
              Market Coverage Index
            </span>
            <span
              className={`text-[11px] font-mono flex items-center gap-1.5 ${
                isLoading ? "text-cyan-400 animate-pulse" : "text-zinc-500"
              }`}
            >
              <Zap className="h-3 w-3" />
              {isLoading ? "Recalculating..." : "Real-time Telemetry"}
            </span>
          </div>

          <div className="flex flex-row items-center gap-4 py-3 sm:py-4">
            <RadialGauge
              percentage={coverageRate}
              isHighlight={delta !== null && delta > 0}
            />

            <div className="space-y-1.5 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xl sm:text-2xl font-bold font-mono text-white tracking-tight tabular-nums">
                  {matchedJobsCount}
                </span>
                <span className="text-xs sm:text-sm font-normal text-zinc-400 font-sans">
                  / <span className="tabular-nums font-mono">{totalTechJobs}</span> postings
                </span>
                {delta !== null && delta > 0 && (
                  <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-950/90 border border-emerald-500/50 text-emerald-300 shadow-sm animate-pulse">
                    <TrendingUp className="h-2.5 w-2.5" />
                    <span className="tabular-nums">+{delta}% Reach</span>
                  </span>
                )}
              </div>
              <div className={`text-xs font-medium ${fitAssessment.color}`}>
                {fitAssessment.label}
              </div>
              <p className="text-[11px] text-zinc-400 leading-snug">
                Your current tech stack matches <span className="font-mono tabular-nums text-zinc-200">{coverageRate}%</span> of active Thai engineering
                postings requiring verified tech clusters.
              </p>
            </div>
          </div>

          <div className="pt-3 border-t border-white/[0.05] flex items-center justify-between text-[11px] font-mono text-zinc-500">
            <span>Deduplication: True</span>
            <span>Dataset: 259 Thailand Tech Jobs</span>
          </div>
        </div>
      </div>

      {/* Bottom Insights Section: Recommendations & Matched Blueprints */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 pt-6 border-t border-white/[0.06]">
        {/* Left Section: ROI Next Best Skills to Learn (6 cols) */}
        <div className="lg:col-span-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-400" />
              <h3 className="text-sm font-semibold text-white tracking-tight">
                Next Best Skills to Learn (Career ROI Engine)
              </h3>
            </div>
            <span className="text-[11px] font-mono text-zinc-500">
              Highest Synergy
            </span>
          </div>

          {data?.recommendedSkills && data.recommendedSkills.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {data.recommendedSkills.slice(0, 4).map((rec) => (
                <div
                  key={rec.name}
                  className="p-3.5 rounded-xl bg-zinc-900/40 border border-white/[0.05] hover:border-cyan-500/30 transition-all flex flex-col justify-between group"
                >
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm font-bold text-white font-mono group-hover:text-cyan-300 transition-colors">
                        {rec.name}
                      </span>
                      <span className="text-[11px] font-mono font-semibold tabular-nums px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-500/30 text-emerald-300">
                        +{rec.unlockPercentage}% reach
                      </span>
                    </div>

                    <div className="text-[11px] text-zinc-400 space-y-1 font-mono">
                      {rec.coOccurrenceRate > 0 && (
                        <div>
                          Companion in{" "}
                          <span className="text-zinc-200 tabular-nums">{rec.coOccurrenceRate}%</span>{" "}
                          of target jobs
                        </div>
                      )}
                      {rec.avgSalary && rec.avgSalary > 0 && (
                        <div className="flex items-center gap-1 text-cyan-300 font-semibold font-mono">
                          <Banknote className="h-3 w-3 text-cyan-400 shrink-0" />
                          <span className="tabular-nums">฿{rec.avgSalary.toLocaleString()}/mo</span>
                          {rec.salarySampleCount ? (
                            <span className="text-zinc-500 font-normal tabular-nums text-[10px]">
                              (n={rec.salarySampleCount})
                            </span>
                          ) : null}
                        </div>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={() => addSkill(rec.name)}
                    className="mt-3 w-full min-h-[44px] py-1.5 px-2 rounded-lg bg-zinc-800/70 hover:bg-cyan-950 border border-white/[0.08] hover:border-cyan-500/40 text-xs font-mono text-zinc-300 hover:text-cyan-300 active:scale-95 transition-all duration-150 flex items-center justify-center gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
                  >
                    <Plus className="h-3 w-3" />
                    <span>Simulate adding {rec.name}</span>
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 rounded-xl bg-zinc-900/30 border border-dashed border-white/[0.06] text-center text-xs font-mono text-zinc-500">
              Select or modify skills to unlock recommended companion synergies.
            </div>
          )}
        </div>

        {/* Right Section: Matched Architecture Blueprints (6 cols) */}
        <div className="lg:col-span-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-cyan-400" />
              <h3 className="text-sm font-semibold text-white tracking-tight">
                Aligned Architecture Portfolio Specs
              </h3>
            </div>
            <Link
              href="/"
              className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 rounded px-1 py-0.5"
            >
              <span>View All</span>
              <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>

          {data?.relevantBlueprints && data.relevantBlueprints.length > 0 ? (
            <div className="space-y-3">
              {data.relevantBlueprints.slice(0, 2).map((bp) => {
                const isFullyUnlocked = bp.matchPercentage === 100;
                const isHighMatch = bp.matchPercentage >= 75 && !isFullyUnlocked;
                return (
                  <Link
                    key={bp.id}
                    href={`/blueprints/${bp.id}`}
                    className={cn(
                      "block p-4 rounded-xl border transition-all duration-150 group active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950",
                      isFullyUnlocked
                        ? "bg-zinc-900/50 border-emerald-500/30 shadow-[0_0_12px_rgba(16,185,129,0.1)] hover:border-emerald-400/50 hover:bg-zinc-900/70"
                        : "bg-zinc-900/40 border-white/[0.05] hover:border-cyan-500/30 hover:bg-zinc-900/60"
                    )}
                  >
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-white/[0.06]">
                            {bp.role}
                          </span>
                          <span className="text-[10px] font-mono text-zinc-500">
                            {bp.difficulty}
                          </span>
                        </div>
                        <h4 className="text-sm font-semibold text-zinc-200 group-hover:text-white transition-colors line-clamp-1">
                          {bp.title}
                        </h4>
                      </div>

                      <div className="text-right shrink-0">
                        {isFullyUnlocked ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-md bg-emerald-950 border border-emerald-500/40 text-emerald-300 shadow-[0_0_10px_rgba(16,185,129,0.2)]">
                            <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                            <span>Fully Unlocked</span>
                          </span>
                        ) : isHighMatch ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-mono font-semibold px-2 py-0.5 rounded-md bg-cyan-950/90 border border-cyan-500/40 text-cyan-200">
                            <span className="tabular-nums">{bp.matchPercentage}% High Match</span>
                          </span>
                        ) : (
                          <span
                            className={cn(
                              "text-xs font-mono font-bold px-2 py-0.5 rounded border tabular-nums",
                              bp.matchPercentage >= 50
                                ? "bg-cyan-950/80 border-cyan-500/40 text-cyan-300"
                                : "bg-zinc-800/80 border-white/[0.06] text-zinc-400"
                            )}
                          >
                            {bp.matchPercentage}% Stack Match
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Matched vs Missing Skill Badges */}
                    <div className="flex flex-wrap gap-1.5 mt-2.5">
                      {bp.matchedSkills.map((skill) => (
                        <span
                          key={skill}
                          className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-500/40 text-cyan-300"
                        >
                          ✓ {skill}
                        </span>
                      ))}
                      {bp.missingSkills.slice(0, 3).map((skill) => (
                        <span
                          key={skill}
                          className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-950 border border-white/[0.06] text-zinc-500"
                        >
                          + {skill}
                        </span>
                      ))}
                      {bp.missingSkills.length > 3 && (
                        <span className="text-[10px] font-mono text-zinc-600 px-1 py-0.5">
                          +{bp.missingSkills.length - 3} more
                        </span>
                      )}
                    </div>
                  </Link>
                );
              })}
            </div>
          ) : (
            <div className="p-6 rounded-xl bg-zinc-900/30 border border-dashed border-white/[0.06] text-center text-xs font-mono text-zinc-500">
              No portfolio blueprints currently available.
            </div>
          )}
        </div>
      </div>
    </SpotlightCard>
  );
}

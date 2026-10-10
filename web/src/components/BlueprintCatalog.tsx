"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight,
  Briefcase,
  Calendar,
  Search,
  SlidersHorizontal,
} from "lucide-react";

import { type GeneratedProject, formatDate, parseTechStack } from "@/lib/turso";
import { cn } from "@/lib/utils";
import SpotlightCard from "@/components/SpotlightCard";

interface BlueprintCatalogProps {
  initialProjects: GeneratedProject[];
}

type RoleCategory = "ALL" | "BACKEND" | "DATA_AI" | "FULLSTACK";

const CATEGORIES: { id: RoleCategory; label: string }[] = [
  { id: "ALL", label: "All Architectures" },
  { id: "BACKEND", label: "Backend & Systems" },
  { id: "DATA_AI", label: "Data & ML Pipelines" },
  { id: "FULLSTACK", label: "Full-Stack & Web" },
];

export default function BlueprintCatalog({ initialProjects }: BlueprintCatalogProps) {
  const [selectedCategory, setSelectedCategory] = useState<RoleCategory>("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredProjects = useMemo(() => {
    return initialProjects.filter((project) => {
      // Category filter
      const roleLower = project.role.toLowerCase();
      let matchesCategory = true;
      if (selectedCategory === "BACKEND") {
        matchesCategory = roleLower.includes("backend");
      } else if (selectedCategory === "DATA_AI") {
        matchesCategory =
          roleLower.includes("data") ||
          roleLower.includes("ai") ||
          roleLower.includes("ml") ||
          roleLower.includes("analyst");
      } else if (selectedCategory === "FULLSTACK") {
        matchesCategory =
          roleLower.includes("full") ||
          roleLower.includes("front") ||
          roleLower.includes("web");
      }

      // Search filter
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !q ||
        project.title.toLowerCase().includes(q) ||
        project.tech_stack.toLowerCase().includes(q) ||
        project.domain.toLowerCase().includes(q);

      return matchesCategory && matchesSearch;
    });
  }, [initialProjects, selectedCategory, searchQuery]);

  return (
    <div className="w-full space-y-8">
      {/* Controls Bar: Role Tabs & Instant Search */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-white/[0.07]">
        {/* Animated Filter Tabs */}
        <div className="flex items-center gap-1.5 p-1 rounded-lg bg-zinc-900/80 border border-white/[0.08] backdrop-blur-md overflow-x-auto">
          {CATEGORIES.map((tab) => {
            const isActive = selectedCategory === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setSelectedCategory(tab.id)}
                className={cn(
                  "relative px-3.5 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-colors duration-200",
                  isActive ? "text-cyan-300" : "text-zinc-400 hover:text-zinc-200"
                )}
              >
                {isActive && (
                  <motion.span
                    layoutId="activeCategoryPill"
                    className="absolute inset-0 rounded-md bg-cyan-950/60 border border-cyan-500/30"
                    transition={{ type: "spring", stiffness: 260, damping: 25 }}
                  />
                )}
                <span className="relative z-10">{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Search Input */}
        <div className="relative min-w-[240px] md:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter by tech, domain, or role..."
            className="w-full bg-zinc-900/60 border border-white/[0.08] focus:border-cyan-500/50 rounded-lg pl-9 pr-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-500 focus:outline-none transition-all"
          />
        </div>
      </div>

      {/* Catalog Grid */}
      <AnimatePresence mode="popLayout">
        {filteredProjects.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center p-16 rounded-xl border border-dashed border-white/[0.08] bg-zinc-950/40 text-center"
          >
            <div className="h-10 w-10 rounded-full bg-zinc-900 flex items-center justify-center mb-3 text-zinc-500">
              <SlidersHorizontal className="h-5 w-5" />
            </div>
            <h3 className="text-sm font-semibold text-zinc-300 mb-1">
              No matching architecture blueprints
            </h3>
            <p className="text-xs text-zinc-500 max-w-sm mb-4">
              Try adjusting your role category filter or search query.
            </p>
            {(selectedCategory !== "ALL" || searchQuery) && (
              <button
                onClick={() => {
                  setSelectedCategory("ALL");
                  setSearchQuery("");
                }}
                className="text-xs font-mono text-cyan-400 hover:underline"
              >
                Clear all filters &rarr;
              </button>
            )}
          </motion.div>
        ) : (
          <motion.div
            layout
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"
          >
            {filteredProjects.map((project, index) => {
              const techStack = parseTechStack(project.tech_stack);
              const specHash = `SPEC-${project.id
                .toString(16)
                .padStart(4, "0")
                .toUpperCase()}`;

              return (
                <motion.div
                  key={project.id}
                  layout
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.96 }}
                  transition={{ duration: 0.2, delay: Math.min(index * 0.04, 0.3) }}
                  className="h-full"
                >
                  <SpotlightCard className="h-full p-6 flex flex-col justify-between hover:border-cyan-500/40 hover:-translate-y-0.5 transition-all duration-300">
                    <div>
                      {/* Header: Role Badge + Spec ID */}
                      <div className="flex items-center justify-between gap-2 mb-3.5">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded text-[11px] font-medium bg-cyan-950/80 border border-cyan-800/60 text-cyan-300">
                          {project.role}
                        </span>
                        <span className="font-mono text-[10px] text-zinc-500 tracking-wider">
                          #{specHash}
                        </span>
                      </div>

                      {/* Blueprint Title */}
                      <Link
                        href={`/blueprints/${project.id}`}
                        className="block font-semibold text-base text-zinc-100 hover:text-cyan-300 transition-colors leading-snug mb-2.5"
                      >
                        {project.title}
                      </Link>

                      {/* Domain & Difficulty */}
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-400 mb-4 font-mono">
                        <div className="flex items-center gap-1.5">
                          <Briefcase className="h-3.5 w-3.5 text-zinc-500" />
                          <span className="truncate max-w-[200px]">
                            {project.domain || "High-Scale Tech"}
                          </span>
                        </div>
                        <span>•</span>
                        <span className="text-zinc-500">{project.difficulty}</span>
                      </div>

                      {/* Tech Stack Pills */}
                      <div className="flex flex-wrap gap-1.5 mb-6">
                        {techStack.slice(0, 5).map((tech) => (
                          <span
                            key={tech}
                            className="font-mono text-[11px] px-2 py-0.5 rounded bg-zinc-800/70 border border-white/[0.06] text-zinc-300"
                          >
                            {tech}
                          </span>
                        ))}
                        {techStack.length > 5 && (
                          <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-zinc-800/40 text-zinc-500">
                            +{techStack.length - 5}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Card Footer */}
                    <div className="pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-zinc-500">
                      <span className="flex items-center gap-1.5 font-mono text-[11px]">
                        <Calendar className="h-3 w-3" />
                        {formatDate(project.created_at)}
                      </span>

                      <Link
                        href={`/blueprints/${project.id}`}
                        className="inline-flex items-center gap-1 text-cyan-400 font-medium hover:translate-x-0.5 transition-transform"
                      >
                        <span>Spec View</span>
                        <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
                    </div>
                  </SpotlightCard>
                </motion.div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

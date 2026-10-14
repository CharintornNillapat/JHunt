"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft,
  BookmarkCheck,
  Briefcase,
  Calendar,
  Check,
  CheckCircle2,
  Code2,
  Copy,
  Download,
  Gauge,
  Hash,
  List,
  Share2,
  Sparkles,
} from "lucide-react";
import type { GeneratedProject } from "@/lib/turso";
import { formatDate, parseTechStack } from "@/lib/format";
import { cn } from "@/lib/utils";

interface BlueprintReaderProps {
  project: GeneratedProject;
}

interface TocHeading {
  id: string;
  text: string;
  level: 2 | 3;
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

function getNodeText(node: unknown): string {
  if (!node) return "";
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(getNodeText).join("");
  if (
    typeof node === "object" &&
    "props" in node &&
    (node as { props: { children?: unknown } }).props.children
  ) {
    return getNodeText((node as { props: { children?: unknown } }).props.children);
  }
  return "";
}

const copyToClipboard = async (text: string): Promise<boolean> => {
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fallback for non-secure context or restricted permissions
  }
  try {
    if (typeof document !== "undefined") {
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.position = "fixed";
      textArea.style.left = "-9999px";
      textArea.style.top = "-9999px";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      const success = document.execCommand("copy");
      document.body.removeChild(textArea);
      return success;
    }
    return false;
  } catch {
    return false;
  }
};

function CodeBlockComponent({
  codeString,
  language,
}: {
  codeString: string;
  language: string;
}) {
  const [copied, setCopied] = useState(false);
  const lineCount = useMemo(() => codeString.split("\n").length, [codeString]);

  const onCopy = async () => {
    await copyToClipboard(codeString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative my-6 rounded-xl border border-white/[0.08] bg-[#0c0d12] overflow-hidden shadow-2xl">
      {/* Terminal Header Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-zinc-900 border-b border-white/[0.06] select-none">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-[#ef4444]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#f59e0b]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#10b981]" />
          </div>
          <span className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider ml-2">
            {language || "SPEC // CONFIG"}
          </span>
          <span className="text-[10px] font-mono text-zinc-400 px-2 py-0.5 rounded bg-zinc-800/80 border border-white/[0.06]">
            {lineCount} {lineCount === 1 ? "line" : "lines"}
          </span>
        </div>

        <button
          onClick={onCopy}
          className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-mono text-zinc-400 hover:text-white bg-zinc-800/60 hover:bg-zinc-800 border border-white/[0.06] transition-colors min-h-[36px] sm:min-h-[32px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-1 focus-visible:ring-offset-zinc-900"
          title="Copy code snippet"
          aria-label={`Copy ${language || "code"} snippet`}
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-emerald-400" />
              <span className="text-emerald-400">Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>Copy</span>
            </>
          )}
          <span className="sr-only" aria-live="polite">
            {copied ? "Code copied to clipboard" : ""}
          </span>
        </button>
      </div>

      {/* Syntax Body */}
      <div className="p-4 overflow-x-auto text-xs sm:text-[13px] leading-relaxed font-mono text-zinc-200">
        <pre className="!bg-transparent !p-0 !m-0 !border-none font-mono">
          <code>{codeString}</code>
        </pre>
      </div>
    </div>
  );
}

export default function BlueprintReader({ project }: BlueprintReaderProps) {
  const [scrollProgress, setScrollProgress] = useState(0);
  const [copiedSpec, setCopiedSpec] = useState(false);
  const [copiedShare, setCopiedShare] = useState(false);
  const [copiedSectionId, setCopiedSectionId] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string>("");

  const techStack = parseTechStack(project.tech_stack);
  const specHash = `SPEC-${project.id
    .toString(16)
    .padStart(4, "0")
    .toUpperCase()}`;

  useEffect(() => {
    const handleScroll = () => {
      const el = document.documentElement;
      const total = el.scrollHeight - window.innerHeight;
      if (total > 0) {
        setScrollProgress((window.scrollY / total) * 100);
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Initial mount hash detection & scroll restoration
  useEffect(() => {
    if (typeof window !== "undefined" && window.location.hash) {
      const targetId = window.location.hash.replace(/^#/, "");
      const timer = setTimeout(() => {
        const el = document.getElementById(targetId);
        if (el) {
          el.scrollIntoView({ behavior: "smooth" });
          setActiveId(targetId);
        }
      }, 200);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleCopySpec = async () => {
    await copyToClipboard(project.spec_markdown || "");
    setCopiedSpec(true);
    setTimeout(() => setCopiedSpec(false), 2000);
  };

  const handleShareLink = async () => {
    if (typeof window !== "undefined") {
      const url = window.location.href;
      await copyToClipboard(url);
      setCopiedShare(true);
      setTimeout(() => setCopiedShare(false), 2000);
    }
  };

  const handleCopySectionLink = async (id: string) => {
    if (typeof window !== "undefined") {
      const url = `${window.location.origin}${window.location.pathname}#${id}`;
      await copyToClipboard(url);
      window.history.replaceState(null, "", `#${id}`);
      setActiveId(id);
      setCopiedSectionId(id);
      setTimeout(() => setCopiedSectionId(null), 2000);
    }
  };

  const handleDownloadMd = () => {
    const filename = `${project.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "blueprint"}-spec.md`;
    const blob = new Blob([project.spec_markdown || ""], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // P1-1: Strip YAML frontmatter and duplicate initial H1 title
  const cleanMarkdown = useMemo(() => {
    return (project.spec_markdown || "")
      .replace(/^---\n[\s\S]*?\n---\n+/, "")
      .replace(/^# .*\n+/, "");
  }, [project.spec_markdown]);

  const headings = useMemo<TocHeading[]>(() => {
    const lines = cleanMarkdown.split("\n");
    const extracted: TocHeading[] = [];
    const counts: Record<string, number> = {};

    for (const line of lines) {
      const match = /^(#{2,3})\s+(.+)$/.exec(line.trim());
      if (match) {
        const level = match[1].length as 2 | 3;
        const rawText = match[2].trim().replace(/[*_`]/g, "");
        let slug = slugify(rawText);
        if (!slug) slug = "section";
        if (counts[slug] !== undefined) {
          counts[slug]++;
          slug = `${slug}-${counts[slug]}`;
        } else {
          counts[slug] = 0;
        }
        extracted.push({ id: slug, text: rawText, level });
      }
    }
    return extracted;
  }, [cleanMarkdown]);

  const currentActiveId = activeId || (headings[0]?.id ?? "");

  useEffect(() => {
    if (headings.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);

        if (visible.length > 0) {
          setActiveId(visible[0].target.id);
        }
      },
      {
        rootMargin: "-100px 0px -60% 0px",
        threshold: 0,
      }
    );

    headings.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [headings]);

  const scrollToHeading = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
      setActiveId(id);
      if (typeof window !== "undefined") {
        window.history.replaceState(null, "", `#${id}`);
      }
    }
  };

  // P1-2: Memoize parsed markdown to prevent re-parsing on scroll events
  const renderedMarkdown = useMemo(() => {
    let headingIdx = 0;
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code(props) {
            const { children, className, ...rest } = props;
            const match = /language-(\w+)/.exec(className || "");
            const codeString = String(children).replace(/\n$/, "");
            const isInline = !match && !codeString.includes("\n");

            if (isInline) {
              return (
                <code
                  className="font-mono text-cyan-300 bg-zinc-900 border border-white/[0.08] px-1.5 py-0.5 rounded text-[12px]"
                  {...rest}
                >
                  {children}
                </code>
              );
            }

            return (
              <CodeBlockComponent
                codeString={codeString}
                language={match ? match[1] : ""}
              />
            );
          },
          blockquote({ children }) {
            return (
              <blockquote className="border-l-2 border-cyan-500/80 bg-cyan-950/20 py-3 px-4 rounded-r-lg my-5 text-zinc-300 font-sans not-italic">
                {children}
              </blockquote>
            );
          },
          table({ children }) {
            return (
              <div className="overflow-x-auto my-6 rounded-xl border border-white/[0.08] bg-[#0c0d12]">
                <table className="w-full text-left text-xs sm:text-sm border-collapse">
                  {children}
                </table>
              </div>
            );
          },
          th({ children }) {
            return (
              <th className="border-b border-white/[0.08] bg-zinc-900 px-4 py-3 font-mono text-xs uppercase tracking-wider text-zinc-300">
                {children}
              </th>
            );
          },
          td({ children }) {
            return (
              <td className="border-b border-white/[0.04] px-4 py-2.5 text-zinc-300 font-sans">
                {children}
              </td>
            );
          },
          h1({ children }) {
            return (
              <h1 className="text-2xl sm:text-3xl font-medium tracking-tight text-zinc-50 pb-3 border-b border-white/[0.08] mt-8 mb-4">
                {children}
              </h1>
            );
          },
          h2(props) {
            const current = headings[headingIdx];
            const id = current?.id || slugify(getNodeText(props.children)) || "section";
            headingIdx++;
            const headingText = getNodeText(props.children);
            return (
              <h2
                id={id}
                className="group relative scroll-mt-32 text-xl sm:text-2xl font-medium tracking-tight text-zinc-100 pb-2 border-b border-white/[0.06] mt-8 mb-3"
              >
                <span className="flex items-center justify-between gap-3">
                  <span>{props.children}</span>
                  <button
                    type="button"
                    onClick={() => handleCopySectionLink(id)}
                    aria-label={`Copy link to section: ${headingText}`}
                    title="Copy link to section"
                    className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity p-1 text-zinc-500 hover:text-cyan-400 rounded min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                  >
                    {copiedSectionId === id ? (
                      <Check className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <Hash className="h-4 w-4" />
                    )}
                  </button>
                </span>
              </h2>
            );
          },
          h3(props) {
            const current = headings[headingIdx];
            const id = current?.id || slugify(getNodeText(props.children)) || "section";
            headingIdx++;
            const headingText = getNodeText(props.children);
            return (
              <h3
                id={id}
                className="group relative scroll-mt-32 text-lg font-medium tracking-tight text-zinc-200 mt-6 mb-2"
              >
                <span className="flex items-center justify-between gap-3">
                  <span>{props.children}</span>
                  <button
                    type="button"
                    onClick={() => handleCopySectionLink(id)}
                    aria-label={`Copy link to section: ${headingText}`}
                    title="Copy link to section"
                    className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity p-1 text-zinc-500 hover:text-cyan-400 rounded min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                  >
                    {copiedSectionId === id ? (
                      <Check className="h-3.5 w-3.5 text-emerald-400" />
                    ) : (
                      <Hash className="h-3.5 w-3.5" />
                    )}
                  </button>
                </span>
              </h3>
            );
          },
          p({ children }) {
            return (
              <p className="text-zinc-300 leading-relaxed my-3 font-sans text-sm sm:text-base">
                {children}
              </p>
            );
          },
          ul({ children }) {
            return (
              <ul className="list-disc list-outside space-y-1.5 my-3 text-zinc-300 text-sm sm:text-base pl-5">
                {children}
              </ul>
            );
          },
          ol({ children }) {
            return (
              <ol className="list-decimal list-outside space-y-1.5 my-3 text-zinc-300 text-sm sm:text-base pl-5">
                {children}
              </ol>
            );
          },
          li({ children }) {
            return (
              <li className="text-zinc-300 leading-relaxed">{children}</li>
            );
          },
          hr() {
            return <hr className="my-8 border-white/[0.08]" />;
          },
        }}
      >
        {cleanMarkdown || "*No specification markdown content available.*"}
      </ReactMarkdown>
    );
  }, [cleanMarkdown, headings, copiedSectionId]);

  return (
    <div className="min-h-screen bg-[#08080a] text-zinc-200 flex flex-col relative">
      {/* 1. Sticky Reading Progress Bar */}
      <div className="fixed top-0 left-0 right-0 h-[2px] z-[60] bg-zinc-900 pointer-events-none">
        <div
          className="h-full bg-gradient-to-r from-cyan-500 via-sky-400 to-indigo-500 transition-all duration-75 motion-reduce:transition-none"
          style={{ width: `${scrollProgress}%` }}
        />
      </div>

      {/* 2. Sticky Action Sub-Header (P1-3: sticky top-16 so it does not slide under top-0 Navbar) */}
      <header className="sticky top-16 z-40 bg-[#08080a] border-b border-white/[0.07]">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          {/* Breadcrumb Navigation */}
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-zinc-400 hover:text-cyan-400 transition-colors group"
            >
              <ArrowLeft className="h-3.5 w-3.5 transform group-hover:-translate-x-1 transition-transform" />
              <span>Back to Catalog</span>
            </Link>
            <span className="text-zinc-600">/</span>
            <span className="font-mono text-xs text-zinc-500 hidden sm:inline">
              #{specHash}
            </span>
          </div>

          {/* Quick-Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleShareLink}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-white/[0.08] transition-all min-h-[36px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
              aria-label="Copy direct blueprint link"
            >
              {copiedShare ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                  <span className="text-emerald-400">Copied Link</span>
                </>
              ) : (
                <>
                  <Share2 className="h-3.5 w-3.5 text-zinc-400" />
                  <span className="hidden sm:inline">Share Link</span>
                  <span className="sm:hidden">Share</span>
                </>
              )}
            </button>

            <button
              onClick={handleCopySpec}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-white/[0.08] transition-all min-h-[36px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
            >
              {copiedSpec ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                  <span className="text-emerald-400">Copied Spec</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5 text-zinc-400" />
                  <span>Copy Raw Spec</span>
                </>
              )}
            </button>

            <button
              onClick={handleDownloadMd}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-cyan-950/40 hover:bg-cyan-950/70 text-cyan-300 hover:text-cyan-200 border border-cyan-800/50 transition-all min-h-[36px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
            >
              <Download className="h-3.5 w-3.5 text-cyan-400" />
              <span className="hidden sm:inline">Download .md</span>
              <span className="sm:hidden">.md</span>
            </button>
          </div>
        </div>

        {/* Screen Reader Live Region for Copy Feedback */}
        <div className="sr-only" aria-live="polite">
          {copiedSectionId
            ? "Link to section copied to clipboard"
            : copiedShare
            ? "Blueprint link copied to clipboard"
            : copiedSpec
            ? "Raw specification copied to clipboard"
            : ""}
        </div>
      </header>

      {/* 3. Hero & Metadata HUD */}
      <section className="border-b border-white/[0.07] bg-gradient-to-b from-[#0d0e12]/60 to-[#08080a] py-10 sm:py-12">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Top Badges */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-cyan-950/80 border border-cyan-800/60 text-cyan-300">
              <Briefcase className="h-3 w-3 text-cyan-400" />
              {project.role}
            </span>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-zinc-900 border border-white/[0.08] text-zinc-400">
              <Gauge className="h-3 w-3 text-sky-400" />
              {project.difficulty || "Production Grade"}
            </span>
            {project.provenance === "fallback" ? (
              <span
                title="Curated offline fallback specification"
                aria-label="Provenance: Curated Archetype"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-950/60 border border-amber-600/40 text-amber-300"
              >
                <BookmarkCheck className="h-3 w-3 text-amber-400" />
                <span>Curated Archetype</span>
              </span>
            ) : (
              <span
                title="Synthesized by Gemini 3.8 Flash from Thailand job postings"
                aria-label="Provenance: Gemini Synthesis"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-cyan-950/60 border border-cyan-500/30 text-cyan-300"
              >
                <Sparkles className="h-3 w-3 text-cyan-400" />
                <span>Gemini Synthesis</span>
              </span>
            )}
            <span className="inline-flex items-center gap-1.5 text-xs text-zinc-500 font-mono ml-auto">
              <Calendar className="h-3.5 w-3.5" />
              {formatDate(project.created_at)}
            </span>
          </div>

          {/* Blueprint Title */}
          <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-zinc-50 mb-6 leading-tight">
            {project.title}
          </h1>

          {/* Metadata Architecture HUD Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 p-4 rounded-xl border border-white/[0.07] bg-[#0c0d12] font-mono text-xs">
            <div>
              <span className="text-[10px] text-zinc-500 uppercase block mb-1">
                Target Role
              </span>
              <span className="text-zinc-200 font-semibold truncate block">
                {project.role}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-zinc-500 uppercase block mb-1">
                Domain Cluster
              </span>
              <span className="text-zinc-200 font-semibold truncate block">
                {project.domain || "Enterprise Systems"}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-zinc-500 uppercase block mb-1">
                Complexity
              </span>
              <span className="text-zinc-200 font-semibold block">
                {project.difficulty || "P95 Staff"}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-zinc-500 uppercase block mb-1">
                Generation Source
              </span>
              <span
                className="text-zinc-200 font-semibold truncate block"
                title={
                  project.provenance === "fallback"
                    ? "Curated Archetype (Offline Fallback)"
                    : "Gemini 3.8 Flash (temperature 0.2)"
                }
              >
                {project.provenance === "fallback"
                  ? "Curated Archetype (Offline Fallback)"
                  : "Gemini 3.8 Flash (temperature 0.2)"}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-zinc-500 uppercase block mb-1">
                Spec Identifier
              </span>
              <span className="text-cyan-400 font-semibold flex items-center gap-1">
                <Hash className="h-3 w-3" />
                {specHash}
              </span>
            </div>
          </div>

          {/* Tech Stack Bar */}
          {techStack.length > 0 && (
            <div className="mt-4 pt-4 border-t border-white/[0.05] flex flex-wrap items-center gap-2">
              <span className="text-xs font-mono text-zinc-500 flex items-center gap-1.5 mr-2">
                <Code2 className="h-3.5 w-3.5 text-cyan-400" />
                Production Stack:
              </span>
              {techStack.map((tech) => (
                <span
                  key={tech}
                  className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-mono bg-zinc-900 border border-white/[0.08] text-cyan-300"
                >
                  <CheckCircle2 className="h-3 w-3 text-cyan-500" />
                  {tech}
                </span>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* 4. Insulated Spec Reading Slab with Sticky TOC */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex-1 w-full bg-[#08080a]">
        {/* Mobile Jump Menu (R-03) */}
        {headings.length > 0 && (
          <div className="lg:hidden mb-8 p-3 rounded-xl border border-white/[0.08] bg-[#0c0d12]/90 backdrop-blur-md">
            <details className="group">
              <summary className="flex items-center justify-between cursor-pointer text-xs font-mono text-zinc-300 select-none py-1 min-h-[44px]">
                <span className="flex items-center gap-2">
                  <List className="h-4 w-4 text-cyan-400" />
                  <span className="font-semibold">Table of Contents</span>
                  <span className="text-zinc-500 text-[11px]">({headings.length} sections)</span>
                </span>
                <span className="text-zinc-500 group-open:rotate-180 transition-transform text-xs">
                  ▼
                </span>
              </summary>
              <nav aria-label="Mobile table of contents" className="mt-3 pt-3 border-t border-white/[0.06] space-y-1 max-h-64 overflow-y-auto">
                {headings.map((h) => {
                  const isActive = currentActiveId === h.id;
                  return (
                    <a
                      key={h.id}
                      href={`#${h.id}`}
                      onClick={(e) => {
                        e.preventDefault();
                        scrollToHeading(h.id);
                      }}
                      className={cn(
                        "block text-xs py-2 px-2.5 rounded transition-colors min-h-[44px] flex items-center",
                        h.level === 3 ? "pl-6 text-zinc-400" : "text-zinc-300 font-medium",
                        isActive
                          ? "bg-cyan-950/60 text-cyan-300 border-l-2 border-cyan-400"
                          : "hover:bg-zinc-800/60 hover:text-zinc-100"
                      )}
                    >
                      {h.text}
                    </a>
                  );
                })}
              </nav>
            </details>
          </div>
        )}

        <div className="lg:grid lg:grid-cols-[1fr_260px] gap-10 items-start">
          <article className="prose prose-invert prose-cyan max-w-none min-w-0">
            {renderedMarkdown}
          </article>

          {/* Sticky Desktop TOC */}
          {headings.length > 0 && (
            <aside className="hidden lg:block sticky top-36 max-h-[calc(100vh-10rem)] overflow-y-auto p-4 rounded-xl border border-white/[0.08] bg-[#0c0d12]/90 backdrop-blur-md">
              <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-400 mb-3 flex items-center gap-1.5 pb-2 border-b border-white/[0.06]">
                <List className="h-3.5 w-3.5 text-cyan-400" />
                <span>Table of Contents</span>
              </h3>
              <nav aria-label="Table of contents" className="space-y-1">
                {headings.map((h) => {
                  const isActive = currentActiveId === h.id;
                  return (
                    <a
                      key={h.id}
                      href={`#${h.id}`}
                      onClick={(e) => {
                        e.preventDefault();
                        scrollToHeading(h.id);
                      }}
                      className={cn(
                        "block text-xs transition-colors rounded py-1.5 pr-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400",
                        h.level === 3 ? "ml-3 text-[11px]" : "font-medium",
                        isActive
                          ? "text-cyan-300 border-l-2 border-cyan-400 bg-cyan-950/30 pl-2.5"
                          : "text-zinc-400 hover:text-zinc-200 pl-2.5 border-l-2 border-transparent"
                      )}
                    >
                      {h.text}
                    </a>
                  );
                })}
              </nav>
            </aside>
          )}
        </div>

        {/* Bottom Navigation */}
        <div className="mt-12 pt-6 border-t border-white/[0.07] flex items-center justify-between">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-cyan-400 font-medium transition-colors group min-h-[44px]"
          >
            <ArrowLeft className="h-4 w-4 transform group-hover:-translate-x-1 transition-transform" />
            <span>Back to All Blueprints</span>
          </Link>
          <a
            href="#top"
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors font-mono min-h-[44px] inline-flex items-center"
          >
            Top of Page &uarr;
          </a>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/[0.07] bg-[#08080a] py-6 text-center text-xs text-zinc-500 font-mono">
        <div className="max-w-4xl mx-auto px-4">
          JHUNT ARCHITECTURE ENGINE &bull; PORTFOLIO ARCHITECTURE SPECIFICATION
        </div>
      </footer>
    </div>
  );
}

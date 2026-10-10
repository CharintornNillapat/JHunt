"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft,
  Briefcase,
  Calendar,
  Check,
  CheckCircle2,
  Code2,
  Copy,
  Download,
  Gauge,
  Hash,
} from "lucide-react";
import { type GeneratedProject, formatDate, parseTechStack } from "@/lib/turso";

interface BlueprintReaderProps {
  project: GeneratedProject;
}

function CodeBlockComponent({
  codeString,
  language,
}: {
  codeString: string;
  language: string;
}) {
  const [copied, setCopied] = useState(false);

  const onCopy = () => {
    navigator.clipboard.writeText(codeString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative my-6 rounded-xl border border-white/[0.08] bg-[#0c0d12] overflow-hidden shadow-2xl">
      {/* Terminal Header Bar with macOS dots */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-zinc-900/90 border-b border-white/[0.06] select-none">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-[#ef4444]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#f59e0b]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#10b981]" />
          </div>
          <span className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider ml-2">
            {language || "SPEC // CONFIG"}
          </span>
        </div>

        <button
          onClick={onCopy}
          className="flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-mono text-zinc-400 hover:text-white bg-zinc-800/60 hover:bg-zinc-800 border border-white/[0.06] transition-colors"
          title="Copy code snippet"
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
        </button>
      </div>

      {/* Syntax Body */}
      <div className="p-4 overflow-x-auto text-[13px] leading-relaxed font-mono text-zinc-200">
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

  const handleCopySpec = () => {
    navigator.clipboard.writeText(project.spec_markdown || "");
    setCopiedSpec(true);
    setTimeout(() => setCopiedSpec(false), 2000);
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

  return (
    <div className="min-h-screen bg-[#08080a] text-zinc-200 flex flex-col relative">
      {/* 1. Sticky Reading Progress Bar */}
      <div className="fixed top-0 left-0 right-0 h-[2px] z-[60] bg-zinc-900/60 pointer-events-none">
        <div
          className="h-full bg-gradient-to-r from-cyan-500 via-sky-400 to-indigo-500 transition-all duration-75"
          style={{ width: `${scrollProgress}%` }}
        />
      </div>

      {/* 2. Sticky Action Sub-Header */}
      <header className="sticky top-0 z-40 bg-[#08080a]/90 backdrop-blur-md border-b border-white/[0.07]">
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
              onClick={handleCopySpec}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-zinc-900/80 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-white/[0.08] transition-all"
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
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-cyan-950/40 hover:bg-cyan-950/70 text-cyan-300 hover:text-cyan-200 border border-cyan-800/50 transition-all"
            >
              <Download className="h-3.5 w-3.5 text-cyan-400" />
              <span className="hidden sm:inline">Download .md</span>
              <span className="sm:hidden">.md</span>
            </button>
          </div>
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
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-xl border border-white/[0.07] bg-[#0c0d12]/90 backdrop-blur-md font-mono text-xs">
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

      {/* 4. Insulated Spec Reading Slab */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex-1 w-full bg-[#08080a]">
        <article className="prose prose-invert prose-cyan max-w-none">
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
                      className="font-mono text-cyan-300 bg-zinc-900/90 border border-white/[0.08] px-1.5 py-0.5 rounded text-[12px]"
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
                  <th className="border-b border-white/[0.08] bg-zinc-900/80 px-4 py-3 font-mono text-xs uppercase tracking-wider text-zinc-300">
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
              h2({ children }) {
                return (
                  <h2 className="text-xl sm:text-2xl font-medium tracking-tight text-zinc-100 pb-2 border-b border-white/[0.06] mt-8 mb-3">
                    {children}
                  </h2>
                );
              },
              h3({ children }) {
                return (
                  <h3 className="text-lg font-medium tracking-tight text-zinc-200 mt-6 mb-2">
                    {children}
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
            {project.spec_markdown ||
              "*No specification markdown content available.*"}
          </ReactMarkdown>
        </article>

        {/* Bottom Navigation */}
        <div className="mt-12 pt-6 border-t border-white/[0.07] flex items-center justify-between">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-cyan-400 font-medium transition-colors group"
          >
            <ArrowLeft className="h-4 w-4 transform group-hover:-translate-x-1 transition-transform" />
            <span>Back to All Blueprints</span>
          </Link>
          <a
            href="#top"
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors font-mono"
          >
            Top of Page &uarr;
          </a>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/[0.07] bg-[#08080a] py-6 text-center text-xs text-zinc-500 font-mono">
        <div className="max-w-4xl mx-auto px-4">
          JHUNT ARCHITECTURE ENGINE &bull; DETERMINISTIC PORTFOLIO SPECIFICATION
        </div>
      </footer>
    </div>
  );
}

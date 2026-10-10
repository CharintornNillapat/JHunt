import Link from "next/link";
import { notFound } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft,
  Briefcase,
  Calendar,
  CheckCircle2,
  Code2,
  Terminal,
} from "lucide-react";
import { getProjectById, parseTechStack } from "@/lib/turso";

export const revalidate = 60;

type Props = {
  params: Promise<{ id: string }>;
};

function formatDate(dateStr: string): string {
  if (!dateStr) return "Recent";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export async function generateMetadata({ params }: Props) {
  const { id } = await params;
  const project = await getProjectById(id);
  if (!project) {
    return {
      title: "Blueprint Not Found | JHunt",
    };
  }
  return {
    title: `${project.title} | JHunt Blueprint`,
    description: `Production portfolio architecture spec for ${project.role} in ${project.domain || "Tech"}.`,
  };
}

export default async function BlueprintDetailPage({ params }: Props) {
  const { id } = await params;
  const project = await getProjectById(id);

  if (!project) {
    return notFound();
  }

  const techStack = parseTechStack(project.tech_stack);

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      {/* Top Header */}
      <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-cyan-400 font-medium transition-colors group"
          >
            <ArrowLeft className="h-4 w-4 transform group-hover:-translate-x-1 transition-transform" />
            <span>Back to Blueprints</span>
          </Link>

          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center">
              <Terminal className="h-4 w-4 text-white" />
            </div>
            <span className="font-extrabold text-base bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              JHunt
            </span>
          </Link>
        </div>
      </header>

      {/* Blueprint Header */}
      <section className="border-b border-slate-800/60 bg-gradient-to-b from-slate-900/50 via-slate-950 to-slate-950 py-10">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Metadata Badges */}
          <div className="flex flex-wrap items-center gap-2.5 mb-4">
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-cyan-950/80 border border-cyan-800/70 text-cyan-300">
              {project.role}
            </span>
            {project.difficulty && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700/60">
                {project.difficulty}
              </span>
            )}
            {project.domain && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-medium bg-slate-900 text-slate-400 border border-slate-800">
                <Briefcase className="h-3 w-3 text-slate-500" />
                {project.domain}
              </span>
            )}
            <span className="inline-flex items-center gap-1 text-xs text-slate-500 font-mono ml-auto">
              <Calendar className="h-3.5 w-3.5" />
              {formatDate(project.created_at)}
            </span>
          </div>

          {/* Title */}
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight text-white mb-6">
            {project.title}
          </h1>

          {/* Tech Stack Banner */}
          {techStack.length > 0 && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs uppercase tracking-wider text-slate-400 font-mono mb-2 flex items-center gap-1.5">
                <Code2 className="h-3.5 w-3.5 text-cyan-400" />
                <span>Target Production Tech Stack</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {techStack.map((tech, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono bg-slate-950 border border-slate-800/80 text-cyan-300 shadow-sm"
                  >
                    <CheckCircle2 className="h-3 w-3 text-cyan-500" />
                    {tech}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Main Markdown Spec Reader */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex-1 w-full">
        <article className="prose prose-invert prose-cyan max-w-none prose-headings:text-slate-100 prose-headings:font-bold prose-h1:text-2xl prose-h2:text-xl prose-h2:border-b prose-h2:border-slate-800 prose-h2:pb-2 prose-h3:text-lg prose-p:text-slate-300 prose-p:leading-relaxed prose-li:text-slate-300 prose-strong:text-cyan-300 prose-code:text-cyan-300 prose-code:bg-slate-900 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none prose-pre:bg-slate-900 prose-pre:border prose-pre:border-slate-800 prose-pre:rounded-xl">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {project.spec_markdown || "*No specification markdown content available.*"}
          </ReactMarkdown>
        </article>

        {/* Bottom Navigation */}
        <div className="mt-12 pt-6 border-t border-slate-800 flex items-center justify-between">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-cyan-400 font-medium transition-colors group"
          >
            <ArrowLeft className="h-4 w-4 transform group-hover:-translate-x-1 transition-transform" />
            <span>Back to All Blueprints</span>
          </Link>
          <a
            href="#top"
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            Back to Top &uarr;
          </a>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950/60 py-6 text-center text-xs text-slate-500">
        <div className="max-w-5xl mx-auto px-4">
          JHunt Market Intelligence System &bull; Production Software Architecture Blueprint
        </div>
      </footer>
    </div>
  );
}

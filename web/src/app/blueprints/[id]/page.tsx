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
} from "lucide-react";
import { formatDate, getProjectById, parseTechStack } from "@/lib/turso";

export const revalidate = 60;

type Props = {
  params: Promise<{ id: string }>;
};

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
  const specHash = `SPEC-${project.id
    .toString(16)
    .padStart(4, "0")
    .toUpperCase()}`;

  return (
    <div className="flex-1 flex flex-col">
      {/* Sub-Header Back Navigation */}
      <div className="border-b border-white/[0.06] bg-zinc-950/40">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between text-xs">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-zinc-400 hover:text-cyan-400 font-medium transition-colors group"
          >
            <ArrowLeft className="h-3.5 w-3.5 transform group-hover:-translate-x-1 transition-transform" />
            <span>Back to Blueprint Catalog</span>
          </Link>
          <span className="font-mono text-zinc-500">#{specHash}</span>
        </div>
      </div>

      {/* Blueprint Header */}
      <section className="border-b border-white/[0.08] bg-gradient-to-b from-zinc-950 via-zinc-900/30 to-zinc-950 py-10">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Metadata Badges */}
          <div className="flex flex-wrap items-center gap-2.5 mb-4">
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-cyan-950/80 border border-cyan-800/70 text-cyan-300">
              {project.role}
            </span>
            {project.difficulty && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-zinc-900 text-zinc-300 border border-white/[0.08]">
                {project.difficulty}
              </span>
            )}
            {project.domain && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-medium bg-zinc-900 text-zinc-400 border border-white/[0.08]">
                <Briefcase className="h-3 w-3 text-zinc-500" />
                {project.domain}
              </span>
            )}
            <span className="inline-flex items-center gap-1 text-xs text-zinc-500 font-mono ml-auto">
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
            <div className="rounded-xl border border-white/[0.08] bg-zinc-900/50 backdrop-blur-md p-4">
              <div className="text-xs uppercase tracking-wider text-zinc-400 font-mono mb-2 flex items-center gap-1.5">
                <Code2 className="h-3.5 w-3.5 text-cyan-400" />
                <span>Target Production Tech Stack</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {techStack.map((tech, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono bg-zinc-950 border border-white/[0.08] text-cyan-300 shadow-sm"
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
        <article className="prose prose-invert prose-cyan max-w-none prose-headings:text-zinc-100 prose-headings:font-bold prose-h1:text-2xl prose-h2:text-xl prose-h2:border-b prose-h2:border-white/[0.08] prose-h2:pb-2 prose-h3:text-lg prose-p:text-zinc-300 prose-p:leading-relaxed prose-li:text-zinc-300 prose-strong:text-cyan-300 prose-code:text-cyan-300 prose-code:bg-zinc-900 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none prose-pre:bg-zinc-900/90 prose-pre:border prose-pre:border-white/[0.08] prose-pre:rounded-xl">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {project.spec_markdown || "*No specification markdown content available.*"}
          </ReactMarkdown>
        </article>

        {/* Bottom Navigation */}
        <div className="mt-12 pt-6 border-t border-white/[0.08] flex items-center justify-between">
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
      <footer className="border-t border-white/[0.08] bg-zinc-950/80 py-6 text-center text-xs text-zinc-500 font-mono">
        <div className="max-w-5xl mx-auto px-4">
          JHUNT ARCHITECTURE ENGINE &bull; REAL-WORLD ENGINEERING PORTFOLIO BLUEPRINT
        </div>
      </footer>
    </div>
  );
}

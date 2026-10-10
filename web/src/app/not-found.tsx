import Link from "next/link";
import { ArrowLeft, FileQuestion } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 min-h-[60vh]">
      <div className="max-w-md w-full text-center border border-white/[0.08] rounded-2xl p-8 bg-zinc-900/50 backdrop-blur-md">
        <div className="h-12 w-12 rounded-xl bg-zinc-800/80 border border-white/[0.08] flex items-center justify-center mx-auto mb-4 text-cyan-400">
          <FileQuestion className="h-6 w-6" />
        </div>
        <h2 className="text-lg font-bold text-white mb-2">Spec Not Found</h2>
        <p className="text-zinc-400 text-xs mb-6">
          The requested architecture blueprint could not be found or has not yet been ingested into Turso Cloud.
        </p>
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Return to Catalog</span>
        </Link>
      </div>
    </div>
  );
}

import Link from "next/link";
import { ArrowLeft, FileQuestion } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 items-center justify-center p-4">
      <div className="max-w-md w-full text-center border border-slate-800 rounded-2xl p-8 bg-slate-900/40">
        <div className="h-14 w-14 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center mx-auto mb-4 text-cyan-400">
          <FileQuestion className="h-7 w-7" />
        </div>
        <h2 className="text-xl font-bold text-white mb-2">Blueprint Not Found</h2>
        <p className="text-slate-400 text-sm mb-6">
          The requested architecture blueprint could not be found or has not yet been synchronized.
        </p>
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-semibold transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Return to Catalog</span>
        </Link>
      </div>
    </div>
  );
}

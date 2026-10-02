import Link from "next/link";
import { Mic, Github, ExternalLink } from "lucide-react";

export default function Footer() {
  const repoUrl =
    process.env.NEXT_PUBLIC_GITHUB_REPO_URL || "https://github.com";

  return (
    <footer className="mt-auto border-t border-slate-200 bg-white py-8 text-sm text-slate-500">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row justify-between items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center text-white">
            <Mic className="w-3.5 h-3.5" />
          </div>
          <span className="font-semibold text-slate-700">Audio Notes Platform</span>
          <span className="text-slate-400">·</span>
          <span>Gnani Innovations Take-Home Assessment</span>
        </div>

        <div className="flex items-center gap-6">
          <Link
            href="/architecture"
            className="hover:text-indigo-600 transition"
          >
            Architecture
          </Link>
          <a
            href={repoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 hover:text-slate-900 transition"
          >
            <Github className="w-4 h-4" />
            <span>GitHub</span>
            <ExternalLink className="w-3 h-3 opacity-60" />
          </a>
        </div>
      </div>
    </footer>
  );
}

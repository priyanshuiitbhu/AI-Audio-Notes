"use client";

import Link from "next/link";
import {
  Layers,
  ArrowRight,
  Database,
  HardDrive,
  Cpu,
  Mic,
  Sparkles,
  ShieldAlert,
  Clock,
  Github,
  CheckCircle2,
  GitBranch,
  Server,
  Cloud,
} from "lucide-react";

export default function ArchitecturePage() {
  const repoUrl =
    process.env.NEXT_PUBLIC_GITHUB_REPO_URL || "https://github.com";

  return (
    <div className="space-y-12 max-w-5xl mx-auto pb-16">
      {/* Title Header */}
      <div className="space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-semibold">
          <Layers className="w-3.5 h-3.5" /> Technical Specification & System Design
        </div>
        <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight">
          System Architecture & Engineering Design
        </h1>
        <p className="text-base text-slate-600 max-w-3xl leading-relaxed">
          A full-stack, distributed platform designed for robust audio transcription and AI-powered summarization, built with Next.js, FastAPI, PostgreSQL, S3-compatible Object Storage, Redis background task workers, and Gnani Prisma ASR.
        </p>

        {/* GitHub Link Bar */}
        <div className="pt-2">
          <div className="inline-flex items-center gap-3 p-3 px-4 rounded-xl bg-white border border-slate-200 shadow-sm text-xs">
            <Github className="w-4 h-4 text-slate-800" />
            <span className="font-semibold text-slate-700">GitHub Repository:</span>
            {process.env.NEXT_PUBLIC_GITHUB_REPO_URL ? (
              <a
                href={process.env.NEXT_PUBLIC_GITHUB_REPO_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-indigo-600 hover:underline"
              >
                {process.env.NEXT_PUBLIC_GITHUB_REPO_URL}
              </a>
            ) : (
              <span className="font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                NEXT_PUBLIC_GITHUB_REPO_URL (Configured via environment)
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Target Architecture Diagram Card */}
      <div className="p-6 sm:p-8 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-6">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <GitBranch className="w-5 h-5 text-indigo-600" />
          End-to-End System Pipeline
        </h2>

        {/* Visual Flow ASCII / Grid */}
        <div className="p-6 rounded-2xl bg-slate-900 text-slate-100 font-mono text-xs overflow-x-auto leading-relaxed shadow-inner">
          <pre>{`
  [ Client Browser: Next.js + TypeScript ]
                 │
                 │ HTTP POST /api/notes/upload (Multipart Audio)
                 ▼
  [ API Gateway / Backend: FastAPI ]
     ├── 1. Validate MIME & File Size (<100MB)
     ├── 2. Save Raw Audio ───────────────► [ Object Storage (S3 / Bucket) ]
     ├── 3. Insert Initial Record (QUEUED) ─► [ PostgreSQL Database ]
     └── 4. Enqueue Job ID ────────────────► [ Redis Queue (RQ / Celery) ]
                                                            │
  ┌─────────────────────────────────────────────────────────┘
  ▼
[ Background Worker Process ]
  │
  ├── 1. Fetch Audio from Storage (Local cache / temp)
  ├── 2. Check Duration & Determine Strategy:
  │      • Short Audio (<=60s)  ──► Gnani REST STT (/stt/v3)
  │      • Long Audio (>60s)    ──► Gnani Batch STT (/stt/v3/batch/jobs) or Audio Chunking
  ├── 3. Save Transcript to PostgreSQL (status: SUMMARIZING)
  ├── 4. Call LLM Service (Structured Executive Summary + Action Items)
  └── 5. Mark COMPLETED in PostgreSQL (completed_at: timestamp)
          `}</pre>
        </div>
      </div>

      {/* 14. Synchronous vs Asynchronous Operations */}
      <div className="p-6 sm:p-8 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <Clock className="w-5 h-5 text-indigo-600" />
          Synchronous vs. Asynchronous Operations
        </h2>
        <p className="text-sm text-slate-600">
          A fundamental tenet of our design is that long-running operations never block HTTP request cycles. The workload is strictly partitioned into synchronous gateway operations and asynchronous worker jobs:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          <div className="p-5 rounded-2xl bg-emerald-50/50 border border-emerald-100 space-y-2">
            <h3 className="text-sm font-bold text-emerald-950 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              Synchronous (Fast HTTP Request)
            </h3>
            <ul className="text-xs text-emerald-900 space-y-1.5 list-disc pl-4">
              <li>File type and payload size validation</li>
              <li>Filename sanitization preventing path traversal</li>
              <li>Streaming audio bytes to object storage bucket</li>
              <li>Creating PostgreSQL initial record with status <code className="bg-emerald-100 px-1 rounded">QUEUED</code></li>
              <li>Dispatching background task ID to queue</li>
              <li>Returning note ID to frontend within &lt; 200ms</li>
              <li>Status polling queries (<code className="bg-emerald-100 px-1 rounded">GET /api/notes/:id/status</code>)</li>
            </ul>
          </div>

          <div className="p-5 rounded-2xl bg-indigo-50/50 border border-indigo-100 space-y-2">
            <h3 className="text-sm font-bold text-indigo-950 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-600" />
              Asynchronous (Worker Pipeline)
            </h3>
            <ul className="text-xs text-indigo-900 space-y-1.5 list-disc pl-4">
              <li>Audio duration detection and sample rate inspection</li>
              <li>Calling Gnani ASR REST API or orchestrating Batch STT jobs</li>
              <li>Incremental progress updates (<code className="bg-indigo-100 px-1 rounded">TRANSCRIBING</code> 30%..70%)</li>
              <li>Database persistence of complete transcribed text</li>
              <li>Prompting LLM with structured meeting note guidelines</li>
              <li>Database persistence of summary, setting status to <code className="bg-indigo-100 px-1 rounded">COMPLETED</code></li>
              <li>Retries with exponential backoff on transient network faults</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Deep-Dive Grid: System Components */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Component 1: Frontend Architecture */}
        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-indigo-600">
            <Server className="w-5 h-5" />
            <h3 className="text-base font-bold text-slate-900">1. Frontend Architecture</h3>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Built using <strong>Next.js 14 App Router</strong> with TypeScript and Tailwind CSS. Employs clean state machine transitions: Idle → Uploading → Queued → Transcribing → Generating Summary → Completed / Failed.
          </p>
          <ul className="text-xs text-slate-600 list-disc pl-4 space-y-1">
            <li>Lightweight HTTP status polling every 2.5s that halts immediately upon completion or failure.</li>
            <li>Client-side validation guards against empty files and unsupported extensions before upload starts.</li>
            <li>Server secrets (Gnani key, LLM key) are never bundled or exposed to the client.</li>
          </ul>
        </div>

        {/* Component 2: Backend Architecture */}
        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-indigo-600">
            <Server className="w-5 h-5" />
            <h3 className="text-base font-bold text-slate-900">2. Backend Architecture</h3>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Powered by <strong>FastAPI (Python)</strong>. Utilizes Pydantic schemas for request/response serialization, dependency injection for database sessions, and custom middleware for request performance telemetry.
          </p>
          <ul className="text-xs text-slate-600 list-disc pl-4 space-y-1">
            <li>Modular service layer isolating Gnani STT, LLM summarization, storage, and job queueing.</li>
            <li>Centralized exception handling preventing technical stack traces from leaking to clients.</li>
            <li>CORS configured to accept allowed frontend origins securely.</li>
          </ul>
        </div>

        {/* Component 3: PostgreSQL Database */}
        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-indigo-600">
            <Database className="w-5 h-5" />
            <h3 className="text-base font-bold text-slate-900">3. PostgreSQL Database</h3>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Relational metadata store utilizing <strong>SQLAlchemy ORM</strong> and managed through <strong>Alembic migrations</strong>.
          </p>
          <ul className="text-xs text-slate-600 list-disc pl-4 space-y-1">
            <li>Tracks note lifecycle: <code>id</code>, <code>file_name</code>, <code>storage_key</code>, <code>status</code>, <code>progress</code>, <code>transcript</code>, <code>summary</code>, <code>error_message</code>.</li>
            <li>Audio binary files are strictly excluded from the database to ensure high performance and prevent DB bloat.</li>
            <li>Indexed by <code>id</code> and <code>status</code> for high-throughput polling.</li>
          </ul>
        </div>

        {/* Component 4: Object Storage */}
        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-indigo-600">
            <HardDrive className="w-5 h-5" />
            <h3 className="text-base font-bold text-slate-900">4. Object Storage</h3>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Provider-independent storage service supporting both <strong>AWS S3 / Supabase Storage / Cloudflare R2</strong> and local filesystem storage for zero-dependency local development.
          </p>
          <ul className="text-xs text-slate-600 list-disc pl-4 space-y-1">
            <li>Safe path hierarchy: <code>audio/&#123;note_id&#125;/&#123;sanitized_filename&#125;</code>.</li>
            <li>Path traversal attacks (<code className="bg-slate-100 px-1 rounded">../</code>) and null-byte injection are neutralized during sanitization.</li>
            <li>Storage credentials remain strictly backend-only.</li>
          </ul>
        </div>

        {/* Component 5: Gnani ASR Integration */}
        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-indigo-600">
            <Mic className="w-5 h-5" />
            <h3 className="text-base font-bold text-slate-900">5. Gnani ASR Integration</h3>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Dedicated service (<code>gnani_service.py</code>) communicating with the official Gnani Prisma v2.5 STT engine via <code>POST https://api.vachana.ai/stt/v3</code>.
          </p>
          <ul className="text-xs text-slate-600 list-disc pl-4 space-y-1">
            <li>Authentication via <code>X-API-Key-ID</code> passed through environment variables.</li>
            <li>Inverse Text Normalization (ITN) enabled (<code>format=transcribe</code>) for proper numeric, currency (₹), and date formatting.</li>
            <li>Supports 10 Indian languages including Hindi, Tamil, Telugu, Kannada, Bengali, and Indian English.</li>
          </ul>
        </div>

        {/* Component 6: Long Audio Processing */}
        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-indigo-600">
            <Cpu className="w-5 h-5" />
            <h3 className="text-base font-bold text-slate-900">6. Long Audio Processing</h3>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Gnani REST STT enforces a 60-second limit (ideal ≤ 30s). To comfortably handle recordings of <strong>2 minutes or longer</strong>, we implement an intelligent multi-strategy pipeline:
          </p>
          <ul className="text-xs text-slate-600 list-disc pl-4 space-y-1">
            <li><strong>Batch STT API:</strong> Creates an async job via <code>/stt/v3/batch/jobs</code>, polls until completion, and fetches full transcript URL.</li>
            <li><strong>Intelligent Chunking:</strong> Splits audio into ~40s segments, transcribes sequentially with progress tracking (e.g. <em>&quot;Transcribing segment 2 of 4...&quot;</em>), and stitches results in sequence.</li>
          </ul>
        </div>

        {/* Component 7: LLM Summarization */}
        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-indigo-600">
            <Sparkles className="w-5 h-5" />
            <h3 className="text-base font-bold text-slate-900">7. LLM Summarization Service</h3>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Dedicated service (<code>summary_service.py</code>) generating structured executive summaries, key discussion points, conclusions, and action items.
          </p>
          <ul className="text-xs text-slate-600 list-disc pl-4 space-y-1">
            <li>Standard OpenAI chat completions API interface (compatible with OpenAI, Groq, OpenRouter, and Gemini).</li>
            <li>Hierarchical chunking for long transcripts (&gt; 2,500 words) to avoid context limit degradation.</li>
            <li>Zero-downtime extractive fallback summarizer if no LLM key is supplied during offline evaluation.</li>
          </ul>
        </div>

        {/* Component 8: Robust Error Handling & Retries */}
        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-indigo-600">
            <ShieldAlert className="w-5 h-5" />
            <h3 className="text-base font-bold text-slate-900">8. Error Handling & Retries</h3>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Distinguishes between transient recoverable errors and terminal failure modes:
          </p>
          <ul className="text-xs text-slate-600 list-disc pl-4 space-y-1">
            <li><strong>Timeouts & 5xx:</strong> Retried up to 3 times with exponential backoff.</li>
            <li><strong>Rate Limits (429):</strong> Exponential backoff delay before retry.</li>
            <li><strong>Authentication & Bad Audio (401/403/400):</strong> Non-retryable; records friendly guidance in database.</li>
            <li><strong>Interactive Retry:</strong> Failed notes can be re-queued via <code>POST /api/notes/:id/retry</code>.</li>
          </ul>
        </div>
      </div>

      {/* Deployment & Production Roadmap */}
      <div className="p-6 sm:p-8 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <Cloud className="w-5 h-5 text-indigo-600" />
          Deployment Architecture & Production Setup
        </h2>
        <p className="text-sm text-slate-600">
          The platform is containerized and cloud-ready for multi-provider deployments:
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 pt-2 text-xs">
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="font-bold text-slate-800 block mb-1">Frontend</span>
            <span className="text-slate-600">Vercel / Cloudflare Pages</span>
          </div>
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="font-bold text-slate-800 block mb-1">Backend API</span>
            <span className="text-slate-600">Render / Fly.io / Railway</span>
          </div>
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="font-bold text-slate-800 block mb-1">Background Worker</span>
            <span className="text-slate-600">Render Worker / Railway</span>
          </div>
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="font-bold text-slate-800 block mb-1">Database & Storage</span>
            <span className="text-slate-600">Managed Postgres + Supabase S3</span>
          </div>
        </div>
      </div>

      {/* What could be improved with more time */}
      <div className="p-6 sm:p-8 rounded-3xl bg-indigo-50/60 border border-indigo-100 space-y-4">
        <h2 className="text-base font-bold text-indigo-950 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-indigo-600" />
          Future Enhancements & Production Roadmap
        </h2>
        <ul className="text-xs text-indigo-900 space-y-2 list-disc pl-5">
          <li><strong>Speaker Diarization:</strong> Enable Gnani speaker diarization (up to 2 speakers) to tag utterances by speaker (e.g., Speaker 1 vs Speaker 2).</li>
          <li><strong>Realtime WebSockets / SSE:</strong> Replace HTTP polling with Server-Sent Events (SSE) or WebSockets for instantaneous real-time streaming transcripts.</li>
          <li><strong>Audio Player with Waveform:</strong> Add an interactive waveform visualizer (e.g. Wavesurfer.js) synchronized with word timestamps.</li>
          <li><strong>Multi-tenant Authentication:</strong> Add OAuth2 / JWT authentication (Clerk, Supabase Auth) for individual user workspaces.</li>
        </ul>
      </div>
    </div>
  );
}

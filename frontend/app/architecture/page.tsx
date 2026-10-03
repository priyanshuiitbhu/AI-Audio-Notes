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
     ├── 1. Validate MIME & File Size
     ├── 2. Save Raw Audio ───────────────► [ Object Storage (S3 / Local Dir) ]
     ├── 3. Insert Initial Record (QUEUED) ─► [ PostgreSQL Database ]
     └── 4. Enqueue Job ID ────────────────► [ Redis Queue (RQ / Thread Fallback) ]
                                                            │
  ┌─────────────────────────────────────────────────────────┘
  ▼
[ Background Worker Process ]
  │
  ├── 1. Fetch Audio from Storage
  ├── 2. Select STT Strategy:
  │      • Short Audio (<=25s) ──► Gnani REST STT (/stt/v3)
  │      • Long Audio (>25s)   ──► Sequential Chunking (/stt/v3) or Batch STT (/stt/v3/batch/jobs)
  │
  ├── 3. Persist Transcript to DB ─────► [ PostgreSQL Database ] (Status: SUMMARIZING)
  │
  ├── 4. Generate Summary ─────────────► [ Google Gemini (google-genai SDK) ]
  │                                           │ (API key strictly server-side)
  │                                           ▼
  └── 5. Persist Summary to DB ────────► [ PostgreSQL Database ] (Status: COMPLETED)
                                                            │
                                                [ Polled by Next.js UI ]
          `}</pre>
        </div>

        {/* AI Responsibilities Card */}
        <div className="p-5 rounded-2xl bg-indigo-50/70 border border-indigo-100 space-y-3">
          <h3 className="text-sm font-bold text-indigo-950 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-600" />
            AI Responsibilities & Strict Separation of Concerns
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="p-3.5 rounded-xl bg-white border border-indigo-100">
              <span className="font-bold text-slate-900 block mb-1">Gnani Prisma v2.5 ASR</span>
              <p className="text-indigo-900 font-semibold mb-1">Speech → Text</p>
              <p className="text-slate-600 leading-relaxed">
                Dedicated exclusively to speech recognition and Inverse Text Normalization (ITN). It converts acoustic waveform data into normalized, verbatim text with currency, dates, and numbers properly formatted.
              </p>
            </div>
            <div className="p-3.5 rounded-xl bg-white border border-indigo-100">
              <span className="font-bold text-slate-900 block mb-1">Google Gemini (google-genai)</span>
              <p className="text-indigo-900 font-semibold mb-1">Transcript → Summary</p>
              <p className="text-slate-600 leading-relaxed">
                Dedicated exclusively to language synthesis. Gemini analyzes the transcript produced by Gnani and outputs structured Executive Overview, Key Points, Important Details, and Action Items.
              </p>
            </div>
          </div>
          <div className="p-3 rounded-xl bg-indigo-100/60 text-indigo-950 text-xs font-medium flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-indigo-700 shrink-0" />
            <span>
              <strong>Zero-Leakage Security Guarantee:</strong> Google Gemini is called <em>only</em> from the backend/background worker. Its API key is never exposed to the browser, client bundle, or network inspector.
            </span>
          </div>
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
            Gnani REST STT enforces a strict duration limit (optimal duration &le; 25s). To comfortably handle recordings of <strong>2 minutes, 10 minutes, or longer</strong> without blocking the user, long audio is processed asynchronously using real, tested strategies:
          </p>
          <ul className="text-xs text-slate-600 list-disc pl-4 space-y-1">
            <li><strong>Deterministic Audio Chunking (Real Implementation):</strong> Pure Python <code>wave</code> splitting partitions audio into ~25s sequential segments without requiring external binaries. Each segment is transcribed sequentially with live progress tracking (e.g. <em>&quot;Transcribing segment 2 of 4...&quot;</em>) and stitched into a unified transcript.</li>
            <li><strong>Batch STT API Integration:</strong> For cloud workflows, the worker can initiate an asynchronous batch job via <code>POST /stt/v3/batch/jobs</code>, poll until completion, and retrieve the final transcript file.</li>
          </ul>
        </div>

        {/* Component 7: Google Gemini Summarization */}
        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-indigo-600">
            <Sparkles className="w-5 h-5" />
            <h3 className="text-base font-bold text-slate-900">7. Google Gemini Summarization</h3>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Dedicated service (<code>summary_service.py</code>) using the official <strong>google-genai</strong> Python SDK to synthesize structured, high-accuracy executive summaries from Gnani transcripts.
          </p>
          <ul className="text-xs text-slate-600 list-disc pl-4 space-y-1">
            <li><strong>Strict Division of Responsibilities:</strong> Gnani is used exclusively for STT; Google Gemini is used exclusively for transcript summarization.</li>
            <li><strong>Transcript Preservation Guarantee:</strong> Transcripts are persisted to PostgreSQL <em>before</em> calling Gemini. If Gemini encounters rate limits or errors, the transcript is never lost.</li>
            <li><strong>Optimized Retry:</strong> Retrying a failed note with an existing transcript skips Gnani ASR and directly triggers Gemini summarization, conserving API credits and time.</li>
            <li><strong>Configurable Model:</strong> Controlled via <code>GEMINI_MODEL</code> (default: <code>gemini-3.5-flash-lite</code>).</li>
            <li><strong>Structured Schema:</strong> Generates uniform Markdown: <code>## Overview</code>, <code>## Key Points</code>, <code>## Important Details</code>, and <code>## Action Items</code> (omitted if no action items exist).</li>
            <li><strong>Zero Key Exposure:</strong> <code>GEMINI_API_KEY</code> is strictly backend-only and never leaked to the client bundle or logs.</li>
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

      {/* Deployment Options */}
      <div className="p-6 sm:p-8 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <Cloud className="w-5 h-5 text-indigo-600" />
          Deployment Options
        </h2>
        <p className="text-sm text-slate-600">
          The platform is cloud-agnostic, containerized, and production-ready for deployment across standard cloud providers:
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 pt-2 text-xs">
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="font-bold text-slate-800 block mb-1">Frontend Option</span>
            <span className="text-slate-600">Vercel / Cloudflare Pages</span>
          </div>
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="font-bold text-slate-800 block mb-1">Backend API Option</span>
            <span className="text-slate-600">Render / Fly.io / Railway</span>
          </div>
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="font-bold text-slate-800 block mb-1">Worker Option</span>
            <span className="text-slate-600">Render Worker / Railway</span>
          </div>
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="font-bold text-slate-800 block mb-1">Database & Storage Option</span>
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

"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  FileAudio,
  Calendar,
  Clock,
  ArrowLeft,
  Copy,
  Check,
  Download,
  RefreshCw,
  Sparkles,
  FileText,
  AlertCircle,
  Loader2,
  Volume2,
} from "lucide-react";
import ProcessingProgress from "@/components/ProcessingProgress";
import { getNoteDetail, getNoteStatus, retryNote } from "@/lib/api";
import { NoteDetail, NoteStatus } from "@/types/note";

export default function NoteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;

  const [note, setNote] = useState<NoteDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedSummary, setCopiedSummary] = useState(false);
  const [copiedTranscript, setCopiedTranscript] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);

  // Load note details
  const fetchDetail = async () => {
    if (!id) return;
    try {
      const data = await getNoteDetail(id);
      setNote(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load note details.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [id]);

  // Polling if note is still processing
  useEffect(() => {
    if (!note) return;
    if (note.status === "COMPLETED" || note.status === "FAILED") return;

    const interval = setInterval(async () => {
      try {
        const st = await getNoteStatus(note.id);
        if (st.status === "COMPLETED" || st.status === "FAILED") {
          // Refresh full note
          fetchDetail();
          clearInterval(interval);
        } else {
          setNote((prev) =>
            prev
              ? {
                  ...prev,
                  status: st.status,
                  progress: st.progress,
                  current_stage: st.current_stage,
                }
              : null
          );
        }
      } catch (err) {
        console.error("Polling error in detail page:", err);
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [note?.id, note?.status]);

  const handleCopy = (text: string, type: "summary" | "transcript") => {
    navigator.clipboard.writeText(text);
    if (type === "summary") {
      setCopiedSummary(true);
      setTimeout(() => setCopiedSummary(false), 2000);
    } else {
      setCopiedTranscript(true);
      setTimeout(() => setCopiedTranscript(false), 2000);
    }
  };

  const handleDownloadTranscript = () => {
    if (!note || !note.transcript) return;
    const blob = new Blob([note.transcript], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${note.file_name.replace(/\.[^/.]+$/, "")}_transcript.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleRetry = async () => {
    if (!note) return;
    setIsRetrying(true);
    try {
      await retryNote(note.id);
      fetchDetail();
    } catch (err: any) {
      alert(err.message || "Failed to retry processing.");
    } finally {
      setIsRetrying(false);
    }
  };

  if (loading) {
    return (
      <div className="p-16 rounded-3xl bg-white border border-slate-200 text-center space-y-3 max-w-4xl mx-auto">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto" />
        <p className="text-sm font-semibold text-slate-700">Loading audio notes...</p>
      </div>
    );
  }

  if (error || !note) {
    return (
      <div className="p-8 rounded-3xl bg-rose-50 border border-rose-200 text-rose-800 max-w-3xl mx-auto space-y-4">
        <div className="flex items-center gap-3">
          <AlertCircle className="w-6 h-6 text-rose-600 shrink-0" />
          <h3 className="text-base font-bold">Could not load note</h3>
        </div>
        <p className="text-sm">{error || "Note not found."}</p>
        <Link
          href="/notes"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Previous Notes
        </Link>
      </div>
    );
  }

  const isProcessing = note.status !== "COMPLETED" && note.status !== "FAILED";
  const formattedDate = new Date(note.created_at).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  const getStatusBadge = () => {
    switch (note.status) {
      case "COMPLETED":
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800">
            ✓ Completed
          </span>
        );
      case "SUMMARIZING":
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 flex items-center gap-1.5">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-700" />
            Generating summary...
          </span>
        );
      case "TRANSCRIBING":
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 flex items-center gap-1.5">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-700" />
            Transcribing audio...
          </span>
        );
      case "FAILED":
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800">
            Processing failed
          </span>
        );
      default:
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-800 flex items-center gap-1.5">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-700" />
            Queued in pipeline...
          </span>
        );
    }
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Top Navigation Row */}
      <div className="flex items-center justify-between">
        <Link
          href="/notes"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-slate-900 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Notes
        </Link>

        <div className="flex items-center gap-2">
          {note.status === "FAILED" && (
            <button
              onClick={handleRetry}
              disabled={isRetrying}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 transition disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRetrying ? "animate-spin" : ""}`} />
              {isRetrying
                ? "Re-queueing..."
                : note.transcript
                ? "Retry Summary"
                : "Retry Processing"}
            </button>
          )}
        </div>
      </div>

      {/* Header Info Card */}
      <div className="p-6 sm:p-8 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
              <FileAudio className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
                {note.file_name}
              </h1>
              <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 mt-1">
                <span className="flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5" />
                  {formattedDate}
                </span>
                <span>·</span>
                <span>{(note.file_size / (1024 * 1024)).toFixed(2)} MB</span>
                {note.duration_seconds && (
                  <>
                    <span>·</span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {Math.round(note.duration_seconds)}s duration
                    </span>
                  </>
                )}
                <span>·</span>
                <span className="uppercase font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-semibold">
                  {note.language_code}
                </span>
              </div>
            </div>
          </div>

          <div>{getStatusBadge()}</div>
        </div>

        {/* Live Progress Bar if still processing or failed */}
        {(isProcessing || note.status === "FAILED") && (
          <div className="pt-2">
            <ProcessingProgress
              status={note.status}
              progress={note.progress}
              currentStage={note.current_stage}
              errorMessage={note.error_message}
              hasTranscript={Boolean(note.transcript && note.transcript.trim())}
              noteId={note.id}
              onRetry={handleRetry}
              isRetrying={isRetrying}
            />
          </div>
        )}
      </div>

      {/* Original Audio Player (when note is completed or audio is stored) */}
      {(note.status === "COMPLETED" || note.transcript) && (
        <div className="p-5 sm:p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-2">
          <div className="flex items-center gap-2 text-slate-800 font-bold text-xs uppercase tracking-wider">
            <Volume2 className="w-4 h-4 text-indigo-600" />
            <span>Original Audio</span>
          </div>
          <audio
            controls
            preload="metadata"
            className="w-full h-10 rounded-lg accent-indigo-600"
            src={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/notes/${note.id}/audio`}
          >
            Your browser does not support the audio element.
          </audio>
        </div>
      )}

      {/* Main Results: Summary and Transcript */}
      {(note.status === "COMPLETED" || note.transcript) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          {/* Summary Card */}
          <div className="p-6 sm:p-8 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2 text-indigo-700">
                <Sparkles className="w-5 h-5" />
                <h2 className="text-base font-bold text-slate-900">Executive Summary</h2>
              </div>

              {note.summary && (
                <button
                  onClick={() => handleCopy(note.summary!, "summary")}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 border border-slate-200 transition"
                >
                  {copiedSummary ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                      <span className="text-emerald-600">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy Summary</span>
                    </>
                  )}
                </button>
              )}
            </div>

            {note.summary ? (
              <div className="prose prose-slate max-w-none text-sm text-slate-700 leading-relaxed whitespace-pre-line">
                {note.summary}
              </div>
            ) : note.status === "FAILED" ? (
              <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs space-y-2">
                <p className="font-semibold">Summary generation failed, but your transcript is preserved below.</p>
                <button
                  onClick={handleRetry}
                  disabled={isRetrying}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-bold transition shadow-sm"
                >
                  <RefreshCw className={`w-3 h-3 ${isRetrying ? "animate-spin" : ""}`} />
                  {isRetrying ? "Re-generating..." : "Retry Summary"}
                </button>
              </div>
            ) : (
              <div className="text-xs text-slate-500 italic">Generating summary with Google Gemini...</div>
            )}
          </div>

          {/* Transcript Card */}
          <div className="p-6 sm:p-8 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2 text-indigo-700">
                <FileText className="w-5 h-5" />
                <h2 className="text-base font-bold text-slate-900">Complete Transcript</h2>
              </div>

              <div className="flex items-center gap-2">
                {note.transcript && (
                  <>
                    <button
                      onClick={() => handleCopy(note.transcript!, "transcript")}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 border border-slate-200 transition"
                      title="Copy full transcript"
                    >
                      {copiedTranscript ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                          <span className="text-emerald-600">Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          <span>Copy</span>
                        </>
                      )}
                    </button>

                    <button
                      onClick={handleDownloadTranscript}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 border border-slate-200 transition"
                      title="Download as text file"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Download</span>
                    </button>
                  </>
                )}
              </div>
            </div>

            <div className="max-h-[500px] overflow-y-auto pr-2 text-sm text-slate-800 leading-relaxed whitespace-pre-wrap font-sans bg-slate-50/60 p-5 rounded-2xl border border-slate-100">
              {note.transcript || "No transcript generated."}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

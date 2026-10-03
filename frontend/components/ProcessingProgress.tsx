"use client";

import Link from "next/link";
import { CheckCircle2, Circle, Loader2, AlertCircle, RefreshCw, ArrowRight, FileText } from "lucide-react";
import { NoteStatus } from "@/types/note";

interface ProcessingProgressProps {
  status: NoteStatus;
  progress: number;
  currentStage: string;
  errorMessage?: string | null;
  hasTranscript?: boolean;
  noteId?: string | null;
  onRetry?: () => void;
  isRetrying?: boolean;
}

interface StepItem {
  id: NoteStatus;
  label: string;
  description: string;
}

const STEPS: StepItem[] = [
  { id: "UPLOADING", label: "Uploading", description: "Sending audio file to storage" },
  { id: "QUEUED", label: "Queued", description: "Enqueued in background processing pipeline" },
  { id: "TRANSCRIBING", label: "Transcribing", description: "Gnani ASR speech-to-text recognition" },
  { id: "SUMMARIZING", label: "Generating summary", description: "Google Gemini structured note synthesis" },
  { id: "COMPLETED", label: "Complete", description: "Transcript and structured summary ready" },
];

function getStepState(
  stepId: NoteStatus,
  currentStatus: NoteStatus,
  hasTranscript: boolean = false
): "completed" | "active" | "pending" | "failed" {
  if (currentStatus === "COMPLETED") {
    return "completed";
  }

  if (currentStatus === "FAILED") {
    if (stepId === "UPLOADING" || stepId === "QUEUED") return "completed";
    if (stepId === "TRANSCRIBING") {
      return hasTranscript ? "completed" : "failed";
    }
    if (stepId === "SUMMARIZING") {
      return hasTranscript ? "failed" : "pending";
    }
    return "pending";
  }

  const order: NoteStatus[] = [
    "UPLOADING",
    "QUEUED",
    "PROCESSING",
    "TRANSCRIBING",
    "SUMMARIZING",
    "COMPLETED",
  ];

  const currentIdx = order.indexOf(currentStatus);
  const stepIdx = order.indexOf(stepId);

  if (stepId === "TRANSCRIBING" && currentStatus === "PROCESSING") {
    return "active";
  }

  if (currentIdx > stepIdx) return "completed";
  if (currentIdx === stepIdx) return "active";
  return "pending";
}

export default function ProcessingProgress({
  status,
  progress,
  currentStage,
  errorMessage,
  hasTranscript = false,
  noteId,
  onRetry,
  isRetrying = false,
}: ProcessingProgressProps) {
  const isFailed = status === "FAILED";
  const isSummaryFailure = Boolean(
    isFailed && (hasTranscript || (errorMessage && errorMessage.toLowerCase().includes("transcript generated successfully")))
  );

  return (
    <div className="w-full bg-white rounded-2xl border border-slate-200 p-6 sm:p-8 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            {isFailed ? (
              <span className="text-rose-600 flex items-center gap-2">
                <AlertCircle className="w-5 h-5" />
                {isSummaryFailure ? "Summary Generation Failed" : "Transcription Failed"}
              </span>
            ) : status === "COMPLETED" ? (
              <span className="text-emerald-600 flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5" /> Audio Processed Successfully
              </span>
            ) : (
              <span className="flex items-center gap-2 text-indigo-700">
                <Loader2 className="w-5 h-5 animate-spin text-indigo-600" />
                Processing your audio
              </span>
            )}
          </h3>
          <p className="text-sm text-slate-600 mt-1">
            {isFailed
              ? errorMessage || "An error occurred during processing."
              : currentStage || "Processing in progress..."}
          </p>
        </div>

        {/* Numerical Progress */}
        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="text-2xl font-black text-slate-900">{progress}%</span>
            <span className="text-xs text-slate-400 block font-medium">pipeline progress</span>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-slate-100 rounded-full h-2.5 mb-8 overflow-hidden">
        <div
          className={`h-2.5 rounded-full transition-all duration-500 ${
            isFailed
              ? isSummaryFailure
                ? "bg-amber-500"
                : "bg-rose-500"
              : status === "COMPLETED"
              ? "bg-emerald-500"
              : "bg-indigo-600"
          }`}
          style={{ width: `${Math.max(5, Math.min(progress, 100))}%` }}
        />
      </div>

      {/* Steps List */}
      <div className="space-y-3">
        {STEPS.map((step) => {
          const state = getStepState(step.id, status, isSummaryFailure);

          return (
            <div
              key={step.id}
              className={`flex items-start gap-3.5 p-3 rounded-xl transition ${
                state === "active"
                  ? "bg-indigo-50/70 border border-indigo-100"
                  : state === "failed"
                  ? "bg-rose-50/70 border border-rose-100"
                  : "bg-transparent"
              }`}
            >
              <div className="mt-0.5 shrink-0">
                {state === "completed" && (
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                )}
                {state === "active" && (
                  <div className="relative flex items-center justify-center w-5 h-5">
                    <span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-indigo-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-600"></span>
                  </div>
                )}
                {state === "pending" && (
                  <Circle className="w-5 h-5 text-slate-300" />
                )}
                {state === "failed" && (
                  <AlertCircle className="w-5 h-5 text-rose-500" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span
                    className={`text-sm font-semibold ${
                      state === "completed"
                        ? "text-slate-800"
                        : state === "active"
                        ? "text-indigo-900 font-bold"
                        : state === "failed"
                        ? "text-rose-900"
                        : "text-slate-400"
                    }`}
                  >
                    {step.label}
                  </span>
                  {state === "active" && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-medium">
                      In progress
                    </span>
                  )}
                  {state === "completed" && (
                    <span className="text-xs text-emerald-600 font-medium">Done</span>
                  )}
                  {state === "failed" && (
                    <span className="text-xs text-rose-600 font-medium">Failed</span>
                  )}
                </div>
                <p
                  className={`text-xs mt-0.5 ${
                    state === "active" ? "text-indigo-700" : "text-slate-500"
                  }`}
                >
                  {state === "active" && currentStage ? currentStage : step.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Failure Callout & Retry Section */}
      {isFailed && (
        <div className="mt-6 p-5 rounded-2xl bg-rose-50/80 border border-rose-200">
          <div className="flex items-start gap-3.5">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div className="flex-1 space-y-2">
              <h4 className="text-sm font-bold text-rose-900">
                {isSummaryFailure
                  ? "Transcript generated successfully, but summary generation failed."
                  : "Transcription failed. We couldn't process this audio."}
              </h4>
              <p className="text-xs text-rose-700 leading-relaxed">
                {isSummaryFailure
                  ? "The transcript is still available and preserved in your library. You can retry summary generation without re-transcribing."
                  : errorMessage || "We couldn't process this audio recording. You can safely retry without re-uploading."}
              </p>

              <div className="flex flex-wrap items-center gap-3 pt-2">
                {onRetry && (
                  <button
                    onClick={onRetry}
                    disabled={isRetrying}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold shadow-sm transition disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isRetrying ? "animate-spin" : ""}`} />
                    {isRetrying
                      ? "Re-queueing..."
                      : isSummaryFailure
                      ? "Retry Summary"
                      : "Retry"}
                  </button>
                )}

                {isSummaryFailure && noteId && (
                  <Link
                    href={`/notes/${noteId}`}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 text-xs font-semibold shadow-sm transition"
                  >
                    <FileText className="w-3.5 h-3.5 text-indigo-600" />
                    <span>View Available Transcript</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

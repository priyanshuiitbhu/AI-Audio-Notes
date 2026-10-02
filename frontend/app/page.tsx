"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  UploadCloud,
  FileAudio,
  X,
  ArrowRight,
  CheckCircle,
  AlertCircle,
  Sparkles,
  ShieldCheck,
  Zap,
} from "lucide-react";
import ProcessingProgress from "@/components/ProcessingProgress";
import { uploadAudio, getNoteStatus, retryNote } from "@/lib/api";
import { NoteStatus } from "@/types/note";

const SUPPORTED_FORMATS = [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"];
const MAX_SIZE_MB = 100;

export default function HomePage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [languageCode, setLanguageCode] = useState<string>("en-IN");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  // Upload & Processing state
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [noteId, setNoteId] = useState<string | null>(null);
  const [processingStatus, setProcessingStatus] = useState<NoteStatus | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [currentStage, setCurrentStage] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);

  // Validate selected file
  const handleFile = (file: File) => {
    setValidationError(null);
    setErrorMessage(null);

    if (file.size === 0) {
      setValidationError("The selected file is empty (0 bytes). Please choose a valid audio file.");
      setSelectedFile(null);
      return;
    }

    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setValidationError(`The file size exceeds the ${MAX_SIZE_MB}MB limit. Please choose a smaller recording.`);
      setSelectedFile(null);
      return;
    }

    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!SUPPORTED_FORMATS.includes(ext)) {
      setValidationError(
        `Unsupported audio format '${ext}'. Please upload an MP3, WAV, M4A, AAC, OGG, or FLAC file.`
      );
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setValidationError(null);
    setErrorMessage(null);
    setProcessingStatus("UPLOADING");
    setProgress(5);
    setCurrentStage("Uploading audio file to storage...");

    try {
      const resp = await uploadAudio(selectedFile, languageCode);
      setNoteId(resp.id);
      setProcessingStatus(resp.status);
      setProgress(resp.progress);
      setCurrentStage(resp.current_stage);
    } catch (err: any) {
      setProcessingStatus("FAILED");
      setErrorMessage(err.message || "Failed to upload audio.");
      setIsUploading(false);
    }
  };

  // Poll status when noteId is available and not completed/failed
  useEffect(() => {
    if (!noteId) return;
    if (processingStatus === "COMPLETED" || processingStatus === "FAILED") return;

    const interval = setInterval(async () => {
      try {
        const statusResp = await getNoteStatus(noteId);
        setProcessingStatus(statusResp.status);
        setProgress(statusResp.progress);
        setCurrentStage(statusResp.current_stage);
        if (statusResp.error_message) {
          setErrorMessage(statusResp.error_message);
        }

        if (statusResp.status === "COMPLETED") {
          clearInterval(interval);
          setIsUploading(false);
        } else if (statusResp.status === "FAILED") {
          clearInterval(interval);
          setIsUploading(false);
        }
      } catch (err: any) {
        console.error("Polling error:", err);
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [noteId, processingStatus]);

  const handleRetry = async () => {
    if (!noteId) return;
    setIsRetrying(true);
    try {
      await retryNote(noteId);
      setProcessingStatus("QUEUED");
      setProgress(10);
      setCurrentStage("Re-queued for processing");
      setErrorMessage(null);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to re-queue note.");
    } finally {
      setIsRetrying(false);
    }
  };

  const resetForm = () => {
    setSelectedFile(null);
    setNoteId(null);
    setProcessingStatus(null);
    setProgress(0);
    setCurrentStage("");
    setErrorMessage(null);
    setIsUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="space-y-12 max-w-4xl mx-auto">
      {/* Hero Header */}
      <div className="text-center space-y-4 pt-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-semibold">
          <Sparkles className="w-3.5 h-3.5" /> Powered by Gnani Prisma v2.5 ASR
        </div>
        <h1 className="text-4xl sm:text-5xl font-black text-slate-900 tracking-tight">
          Turn your audio into notes
        </h1>
        <p className="text-lg text-slate-600 max-w-2xl mx-auto">
          Upload any audio file to transcribe with industry-leading speech recognition and generate structured AI summaries with key action items.
        </p>
      </div>

      {/* Main Card: Upload or Processing */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 sm:p-10 shadow-sm transition">
        {processingStatus ? (
          /* Processing or Completed View */
          <div className="space-y-6">
            <ProcessingProgress
              status={processingStatus}
              progress={progress}
              currentStage={currentStage}
              errorMessage={errorMessage}
              onRetry={handleRetry}
              isRetrying={isRetrying}
            />

            {processingStatus === "COMPLETED" && noteId && (
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-5 rounded-2xl bg-indigo-50 border border-indigo-100">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white">
                    <CheckCircle className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900">Your notes are ready!</h4>
                    <p className="text-xs text-slate-600">Full transcript and executive summary are saved.</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 w-full sm:w-auto">
                  <button
                    onClick={resetForm}
                    className="flex-1 sm:flex-none px-4 py-2 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl transition"
                  >
                    Upload Another
                  </button>
                  <button
                    onClick={() => router.push(`/notes/${noteId}`)}
                    className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-md shadow-indigo-200 transition"
                  >
                    <span>View Note</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Upload Interface */
          <div className="space-y-6">
            {/* Drag & Drop Zone */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center cursor-pointer transition ${
                isDragOver
                  ? "border-indigo-500 bg-indigo-50/50 scale-[0.99]"
                  : "border-slate-300 hover:border-indigo-400 hover:bg-slate-50/80"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept={SUPPORTED_FORMATS.join(",")}
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    handleFile(e.target.files[0]);
                  }
                }}
                className="hidden"
              />

              <div className="w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-4 border border-indigo-100 shadow-sm">
                <UploadCloud className="w-8 h-8" />
              </div>

              <h3 className="text-base font-bold text-slate-800">
                Click to browse or drag & drop audio here
              </h3>
              <p className="text-xs text-slate-500 mt-1.5">
                MP3, WAV, M4A, AAC, OGG, or FLAC up to {MAX_SIZE_MB}MB
              </p>
              <p className="text-xs text-indigo-600 font-medium mt-3">
                Comfortably handles long recordings (2+ minutes) via asynchronous pipeline
              </p>
            </div>

            {/* Validation Error Banner */}
            {validationError && (
              <div className="flex items-center gap-3 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm">
                <AlertCircle className="w-5 h-5 shrink-0 text-rose-600" />
                <span>{validationError}</span>
              </div>
            )}

            {/* Selected File Details */}
            {selectedFile && (
              <div className="flex items-center justify-between p-4 rounded-2xl bg-slate-50 border border-slate-200">
                <div className="flex items-center gap-3.5 min-w-0">
                  <div className="w-10 h-10 rounded-xl bg-white border border-slate-200 flex items-center justify-center text-indigo-600 shrink-0">
                    <FileAudio className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-900 truncate">
                      {selectedFile.name}
                    </p>
                    <p className="text-xs text-slate-500">
                      {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · {selectedFile.type || "Audio file"}
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => setSelectedFile(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition"
                  aria-label="Remove selected file"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            )}

            {/* Language Selection & Submit Row */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 pt-2 border-t border-slate-100">
              <div className="flex items-center gap-2">
                <label htmlFor="language_code" className="text-xs font-semibold text-slate-600">
                  Audio Language:
                </label>
                <select
                  id="language_code"
                  value={languageCode}
                  onChange={(e) => setLanguageCode(e.target.value)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-700 bg-white hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                >
                  <option value="en-IN">English (India) - en-IN</option>
                  <option value="hi-IN">Hindi - hi-IN</option>
                  <option value="bn-IN">Bengali - bn-IN</option>
                  <option value="te-IN">Telugu - te-IN</option>
                  <option value="ta-IN">Tamil - ta-IN</option>
                  <option value="mr-IN">Marathi - mr-IN</option>
                  <option value="kn-IN">Kannada - kn-IN</option>
                  <option value="gu-IN">Gujarati - gu-IN</option>
                  <option value="ml-IN">Malayalam - ml-IN</option>
                  <option value="pa-IN">Punjabi - pa-IN</option>
                </select>
              </div>

              <button
                onClick={handleUpload}
                disabled={!selectedFile || isUploading}
                className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold shadow-md shadow-indigo-200 transition disabled:opacity-50 disabled:pointer-events-none"
              >
                <span>Upload & Process Audio</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Feature Highlights Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-4">
        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-4">
            <Zap className="w-5 h-5" />
          </div>
          <h4 className="text-sm font-bold text-slate-900">Gnani ASR Engine</h4>
          <p className="text-xs text-slate-600 mt-1">
            Transcribes speech with Prisma v2.5 models and Inverse Text Normalization (ITN).
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-4">
            <Sparkles className="w-5 h-5" />
          </div>
          <h4 className="text-sm font-bold text-slate-900">AI Summarization</h4>
          <p className="text-xs text-slate-600 mt-1">
            Extracts executive summaries, key decisions, and concrete action items automatically.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-4">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <h4 className="text-sm font-bold text-slate-900">Long Audio Architecture</h4>
          <p className="text-xs text-slate-600 mt-1">
            Background workers with progress tracking handle recordings of 2+ minutes effortlessly.
          </p>
        </div>
      </div>
    </div>
  );
}

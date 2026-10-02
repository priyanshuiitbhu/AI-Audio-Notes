"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  FileAudio,
  Calendar,
  Clock,
  ArrowRight,
  AlertCircle,
  Loader2,
  RefreshCw,
  FolderOpen,
  Trash2,
} from "lucide-react";
import { getNotes, deleteNote } from "@/lib/api";
import { NoteListItem } from "@/types/note";

export default function NotesPage() {
  const [notes, setNotes] = useState<NoteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchNotes = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getNotes();
      setNotes(data);
    } catch (err: any) {
      setError(err.message || "Failed to load previous notes.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotes();
  }, []);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (!confirm("Are you sure you want to delete this audio note?")) return;

    setDeletingId(id);
    try {
      await deleteNote(id);
      setNotes((prev) => prev.filter((n) => n.id !== id));
    } catch (err: any) {
      alert(err.message || "Failed to delete note.");
    } finally {
      setDeletingId(null);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
            Completed
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800">
            Processing failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
            <Loader2 className="w-3 h-3 animate-spin" />
            Processing...
          </span>
        );
    }
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tight">Previous Notes</h1>
          <p className="text-sm text-slate-500 mt-1">
            Access, view, or export your previously transcribed recordings.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchNotes}
            disabled={loading}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 transition shadow-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-md shadow-indigo-200 transition"
          >
            Upload Audio
          </Link>
        </div>
      </div>

      {/* Content states */}
      {loading ? (
        <div className="p-16 rounded-3xl bg-white border border-slate-200 text-center space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto" />
          <p className="text-sm font-semibold text-slate-700">Loading previous notes...</p>
        </div>
      ) : error ? (
        <div className="p-8 rounded-3xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-bold">Failed to load notes</h4>
            <p className="text-xs text-rose-700 mt-1">{error}</p>
            <button
              onClick={fetchNotes}
              className="mt-3 text-xs font-bold underline hover:text-rose-900"
            >
              Try Again
            </button>
          </div>
        </div>
      ) : notes.length === 0 ? (
        /* Empty State */
        <div className="p-16 rounded-3xl bg-white border border-slate-200 text-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto">
            <FolderOpen className="w-8 h-8" />
          </div>
          <div className="space-y-1">
            <h3 className="text-lg font-bold text-slate-800">You haven&apos;t uploaded any audio yet.</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Upload meeting audio, voice memos, or lectures to get automatic transcripts and AI summaries.
            </p>
          </div>
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-md shadow-indigo-200 transition"
          >
            Upload your first recording
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      ) : (
        /* Notes Grid / List */
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {notes.map((note) => {
            const formattedDate = new Date(note.created_at).toLocaleDateString("en-US", {
              year: "numeric",
              month: "long",
              day: "numeric",
            });

            return (
              <div
                key={note.id}
                className="group relative flex flex-col justify-between p-6 rounded-2xl bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-md transition"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                        <FileAudio className="w-4 h-4" />
                      </div>
                      <h3 className="text-sm font-bold text-slate-900 truncate">
                        {note.file_name}
                      </h3>
                    </div>

                    <div className="shrink-0">{getStatusBadge(note.status)}</div>
                  </div>

                  {/* Metadata Row */}
                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 mb-4">
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
                          {Math.round(note.duration_seconds)}s
                        </span>
                      </>
                    )}
                  </div>

                  {/* Summary preview */}
                  <p className="text-xs text-slate-600 line-clamp-3 mb-4 leading-relaxed">
                    {note.summary_preview ? (
                      `"${note.summary_preview}"`
                    ) : note.status === "COMPLETED" ? (
                      "Transcript generated successfully."
                    ) : note.status === "FAILED" ? (
                      <span className="text-rose-600">Failed to process audio file.</span>
                    ) : (
                      <span className="text-amber-600">{note.current_stage || "Processing..."}</span>
                    )}
                  </p>
                </div>

                {/* Bottom Actions */}
                <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                  <button
                    onClick={(e) => handleDelete(note.id, e)}
                    disabled={deletingId === note.id}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition"
                    title="Delete note"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>

                  <Link
                    href={`/notes/${note.id}`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-indigo-600 hover:text-white hover:bg-indigo-600 bg-indigo-50 transition"
                  >
                    <span>Open</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

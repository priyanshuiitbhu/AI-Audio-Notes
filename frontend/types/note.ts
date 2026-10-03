export type NoteStatus =
  | "UPLOADING"
  | "QUEUED"
  | "PROCESSING"
  | "TRANSCRIBING"
  | "SUMMARIZING"
  | "COMPLETED"
  | "FAILED";

export interface NoteUploadResponse {
  id: string;
  file_name: string;
  status: NoteStatus;
  progress: number;
  current_stage: string;
  message: string;
}

export interface NoteStatusResponse {
  id: string;
  status: NoteStatus;
  progress: number;
  current_stage: string;
  error_message?: string | null;
  has_transcript?: boolean;
  completed_at?: string | null;
}

export interface NoteListItem {
  id: string;
  file_name: string;
  file_size: number;
  mime_type: string;
  duration_seconds?: number | null;
  status: NoteStatus;
  progress: number;
  current_stage: string;
  summary_preview?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface NoteDetail {
  id: string;
  file_name: string;
  storage_key: string;
  file_size: number;
  mime_type: string;
  duration_seconds?: number | null;
  language_code: string;
  status: NoteStatus;
  progress: number;
  current_stage: string;
  transcript?: string | null;
  summary?: string | null;
  error_message?: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface HealthResponse {
  status: string;
  database: string;
  redis: string;
  worker: string;
  storage: string;
  gnani_configured: boolean;
  llm_configured: boolean;
  gemini_configured?: boolean;
  timestamp: string;
}

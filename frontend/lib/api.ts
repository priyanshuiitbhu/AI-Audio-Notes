import {
  NoteUploadResponse,
  NoteStatusResponse,
  NoteListItem,
  NoteDetail,
  HealthResponse,
} from "@/types/note";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorMsg = `Server error (${res.status})`;
    try {
      const errorJson = await res.json();
      errorMsg = errorJson.detail || errorJson.message || errorMsg;
    } catch {
      // Ignore JSON parse error on non-json response
    }
    throw new ApiError(errorMsg, res.status);
  }
  return res.json() as Promise<T>;
}

export async function uploadAudio(
  file: File,
  languageCode: string = "en-IN"
): Promise<NoteUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("language_code", languageCode);

  try {
    const res = await fetch(`${API_BASE_URL}/notes/upload`, {
      method: "POST",
      body: formData,
    });
    return await handleResponse<NoteUploadResponse>(res);
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(
      "Unable to connect to the backend server. Please verify your connection.",
      0
    );
  }
}

export async function getNotes(skip = 0, limit = 100): Promise<NoteListItem[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/notes?skip=${skip}&limit=${limit}`, {
      cache: "no-store",
    });
    return await handleResponse<NoteListItem[]>(res);
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError("Failed to fetch previous notes.", 0);
  }
}

export async function getNoteDetail(id: string): Promise<NoteDetail> {
  try {
    const res = await fetch(`${API_BASE_URL}/notes/${id}`, {
      cache: "no-store",
    });
    return await handleResponse<NoteDetail>(res);
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError("Failed to load note details.", 0);
  }
}

export async function getNoteStatus(id: string): Promise<NoteStatusResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/notes/${id}/status`, {
      cache: "no-store",
    });
    return await handleResponse<NoteStatusResponse>(res);
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError("Failed to check note status.", 0);
  }
}

export async function retryNote(
  id: string
): Promise<{ id: string; status: string; message: string }> {
  const res = await fetch(`${API_BASE_URL}/notes/${id}/retry`, {
    method: "POST",
  });
  return await handleResponse<{ id: string; status: string; message: string }>(res);
}

export async function deleteNote(
  id: string
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE_URL}/notes/${id}`, {
    method: "DELETE",
  });
  return await handleResponse<{ success: boolean; message: string }>(res);
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`, {
    cache: "no-store",
  });
  return await handleResponse<HealthResponse>(res);
}

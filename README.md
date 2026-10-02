# Audio Notes Platform

A production-grade, distributed web platform that transcribes spoken audio using the **Gnani Prisma v2.5 ASR API** and generates structured executive notes using **Google Gemini** (`google-genai` SDK).

Designed and engineered for the **Gnani Innovations Private Limited Take-Home Assessment**.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Local Setup](#local-setup)
- [Database Setup](#database-setup)
- [Storage Setup](#storage-setup)
- [Redis & Background Workers](#redis--background-workers)
- [Backend Setup](#backend-setup)
- [Worker Setup](#worker-setup)
- [Frontend Setup](#frontend-setup)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Deployment Guide](#deployment-guide)
- [API Endpoints](#api-endpoints)
- [Long Audio Processing](#long-audio-processing)
- [Error Handling & Retries](#error-handling--retries)
- [Design Decisions](#design-decisions)
- [Future Improvements](#future-improvements)

---

## Overview

The **Audio Notes Platform** solves the challenge of capturing and structuring spoken information from meetings, lectures, voice memos, and call recordings. 

Users upload an audio recording in any standard format (MP3, WAV, M4A, AAC, OGG, FLAC). The backend immediately persists the audio to object storage, enqueues an asynchronous background job, and returns control to the user. An autonomous worker streams the recording to Gnani's Speech-to-Text API, saves the verbatim and normalized transcript to PostgreSQL, prompts an LLM to extract key discussion points and action items, and presents the resulting notes on an interactive, responsive Next.js frontend.

---

## Key Features

- **Gnani Prisma v2.5 Speech Recognition**: Direct integration with Gnani ASR (`https://api.vachana.ai`) with Inverse Text Normalization (ITN) formatting currency, dates, and numbers.
- **Multilingual Support**: Supports 10 Indian languages (`en-IN`, `hi-IN`, `bn-IN`, `ta-IN`, `te-IN`, `mr-IN`, `kn-IN`, `gu-IN`, `ml-IN`, `pa-IN`).
- **Comfortable Long Audio Processing**: Handles recordings of 2 minutes or longer via Gnani STT Batch processing and deterministic audio segment chunking.
- **Stage-Based Realtime Progress**: The UI never freezes or looks stuck; it clearly reflects current states: `Uploading` → `Queued` → `Transcribing` → `Generating summary` → `Completed` / `Failed`.
- **Google Gemini Structured Summaries**: Dedicated summarization using Google Gemini (`google-genai` SDK) into an Executive Overview, Key Points, Important Details, and Action Items.
- **Transcript Preservation Guarantee**: Transcripts are persisted to PostgreSQL *before* calling Gemini. If Gemini encounters rate limits or errors, the transcript is never lost.
- **Optimized Retry Pipeline**: Retrying a failed note skips Gnani ASR if the transcript is already saved, saving API credits and accelerating completion.
- **Resilient Error Recovery & Retries**: Distinguishes transient network errors from permanent invalid files; allows one-click reprocessing via `POST /api/notes/:id/retry`.
- **Persistent Notes Library**: Full CRUD support to search, reopen, review, copy, and download previous transcripts and notes.
- **Zero-Secret Client Security**: All API keys (Gnani, Gemini, Storage) live exclusively on the backend server.
- **Interactive `/architecture` Page**: Complete built-in system documentation with data flow diagrams and engineering rationale.

---

## Architecture

```
                          USER / BROWSER
                                │
                                ▼
                       ┌─────────────────┐
                       │ Next.js 14 (TS) │
                       │    Frontend     │
                       └────────┬────────┘
                                │
                                │ REST API (HTTP)
                                ▼
                       ┌─────────────────┐
                       │ FastAPI Backend │
                       └────────┬────────┘
                                │
               ┌────────────────┴────────────────┐
               │                                 │
               ▼                                 ▼
      ┌──────────────────┐             ┌──────────────────┐
      │ PostgreSQL DB    │             │  Object Storage  │
      │ (Alembic Schema) │             │ (S3 / Local Dir) │
      └──────────────────┘             └────────┬─────────┘
                                                │
                                                ▼
                                       ┌──────────────────┐
                                       │ Background Task  │
                                       │  Worker (RQ)     │
                                       └────────┬─────────┘
                                                │
                               ┌────────────────┴────────────────┐
                               ▼                                 ▼
                      ┌──────────────────┐             ┌──────────────────┐
                      │ Gnani Prisma ASR │             │ LLM Summarization│
                      │  (STT REST/Batch)│             │ (OpenAI / Groq)  │
                      └──────────────────┘             └──────────────────┘
```

### Synchronous vs. Asynchronous Operations

| Operation Type | Responsibility | Performance Target |
| :--- | :--- | :--- |
| **Synchronous (HTTP Request)** | File validation, audio upload to object storage, PostgreSQL record creation (`QUEUED`), background task dispatch, status polling (`GET /api/notes/:id/status`). | Response delivered in `< 250ms` |
| **Asynchronous (Worker Job)** | Fetching stored audio, audio duration analysis, calling Gnani ASR REST / Batch STT, updating progress stages (`30%..75%`), LLM prompt synthesis, and final database commit. | Decoupled from HTTP lifecycle; handles multi-minute recordings without timeout |

---

## Tech Stack

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, Lucide React
- **Backend API**: FastAPI, Python 3.10+, Pydantic v2, Uvicorn
- **Database**: PostgreSQL 16 (production), SQLite (zero-dependency local test mode), SQLAlchemy ORM, Alembic migrations
- **Storage**: S3-compatible Object Storage (AWS S3, Supabase Storage, Cloudflare R2, MinIO) + Local filesystem provider
- **Background Jobs**: Redis 7 + Python RQ (with automatic daemon thread fallback for lightweight local dev)
- **AI / Speech**: Gnani Prisma v2.5 Speech-to-Text API (`api.vachana.ai`)
- **AI / LLM**: Google Gemini (`google-genai` official Python SDK, default model: `gemini-3.5-flash-lite`) with structured prompt engineering & extractive fallback

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── notes.py          # REST endpoints (upload, list, detail, status, retry, delete)
│   │   ├── models/
│   │   │   └── note.py           # SQLAlchemy Note model and NoteStatus enum
│   │   ├── schemas/
│   │   │   └── note.py           # Pydantic v2 schemas and validation models
│   │   ├── services/
│   │   │   ├── gnani_service.py   # Dedicated Gnani STT client (REST, Batch, Retries)
│   │   │   ├── storage_service.py # S3 and Local filesystem storage abstraction
│   │   │   ├── summary_service.py # Google Gemini summarization with exponential retries
│   │   │   └── job_service.py     # Task queue dispatcher (Redis RQ & Thread fallback)
│   │   ├── utils/
│   │   │   └── audio_utils.py     # Filename sanitization, wave splitter, format checks
│   │   ├── workers/
│   │   │   └── audio_worker.py    # Background pipeline orchestrator
│   │   ├── config.py              # Application settings and environment variables
│   │   ├── database.py            # SQLAlchemy engine, session maker, base
│   │   └── main.py                # FastAPI initialization, CORS, health endpoint
│   ├── migrations/                # Alembic migration revisions
│   ├── tests/
│   │   ├── test_api.py            # API & worker pipeline integration tests
│   │   └── test_gemini_summary.py # Gemini summarization, retry, preservation, and edge-case tests
│   ├── requirements.txt           # Python dependencies (includes google-genai)
│   ├── pytest.ini                 # Pytest configuration
│   └── worker.py                  # Standalone RQ worker runner script
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx               # Homepage: Drag-and-drop audio upload & live progress
│   │   ├── notes/
│   │   │   ├── page.tsx           # Previous Notes listing & status filters
│   │   │   └── [id]/page.tsx      # Note detail: Markdown summary & full transcript
│   │   ├── architecture/page.tsx  # Architecture documentation & system design
│   │   ├── layout.tsx             # Root layout with responsive navigation
│   │   └── globals.css            # Tailwind directives and custom styling
│   ├── components/
│   │   ├── Navbar.tsx             # Responsive navigation bar
│   │   ├── Footer.tsx             # Footer with GitHub link
│   │   └── ProcessingProgress.tsx # Stage-based processing card with retry action
│   ├── lib/
│   │   └── api.ts                 # Typed backend API client
│   ├── types/
│   │   └── note.ts                # TypeScript interfaces
│   ├── package.json               # Node.js dependencies
│   └── tailwind.config.js         # Tailwind configuration
│
├── docker-compose.yml             # Docker Compose for PostgreSQL & Redis
├── .env.example                   # Annotated environment template
├── .gitignore                     # Git ignore rules (secrets, venv, caches)
└── README.md                      # Complete system documentation
```

---

## Environment Variables

Copy `.env.example` to `.env` in the root (or `backend/.env`):

```bash
cp .env.example .env
```

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL or SQLite connection string | `sqlite:///./audionotes.db` or `postgresql://postgres:postgrespassword@localhost:5432/audionotes` |
| `REDIS_URL` | Redis URL for task queue | `redis://localhost:6379/0` |
| `GNANI_API_KEY` | Gnani Prisma ASR API Key (Backend only) | `vach_1ytE2CY5X...` |
| `GNANI_API_BASE_URL` | Gnani API Base URL | `https://api.vachana.ai` |
| `DEFAULT_LANGUAGE` | Default audio language code | `en-IN` |
| `STORAGE_PROVIDER` | `local` (saves to disk) or `s3` (cloud bucket) | `local` |
| `STORAGE_LOCAL_DIR` | Directory for local audio files | `storage` |
| `STORAGE_BUCKET` | S3 bucket name | `audionotes` |
| `STORAGE_ENDPOINT` | Custom S3 endpoint (for Supabase / MinIO / R2) | Optional |
| `STORAGE_ACCESS_KEY` | S3 access key ID | Optional |
| `STORAGE_SECRET_KEY` | S3 secret access key | Optional |
| `GEMINI_API_KEY` | Google Gemini API Key (Backend only, never exposed to frontend) | `AIzaSy...` |
| `GEMINI_MODEL` | Google Gemini Model Identifier | `gemini-3.5-flash-lite` |
| `NEXT_PUBLIC_API_URL` | FastAPI backend URL for frontend | `http://localhost:8000/api` |
| `NEXT_PUBLIC_GITHUB_REPO_URL` | GitHub repository link for `/architecture` | `https://github.com/your-username/Audio-Notes-Platform` |

---

## Local Setup

### 1. Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- (Optional) Docker for PostgreSQL and Redis

### 2. Quick Start with Docker (Recommended for Full Stack)

Start PostgreSQL and Redis:

```bash
docker compose up -d
```

### 3. Backend Setup

```bash
# Navigate to backend and create virtual environment
cd backend
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI backend
uvicorn app.main:app --reload --port 8000
```

The API documentation will be available at: `http://localhost:8000/docs`

### 4. Background Worker Setup

In a separate terminal window:

```bash
cd backend
source venv/bin/activate

# Start the background RQ worker (listens to Redis queue)
python worker.py
```

> **Note on Zero-Dependency Mode**: If Redis is not running locally, the backend automatically detects this and processes jobs using a background worker thread. You will never encounter a crash due to missing local Redis.

### 5. Frontend Setup

In a third terminal window:

```bash
cd frontend
npm install
npm run dev
```

Open your browser at `http://localhost:3000`.

---

## Testing

Automated tests cover all core features with **100% mocked external APIs** (no real credits or internet requests during testing):

```bash
cd backend
source venv/bin/activate
pytest -v
```

### Test Suite Coverage (22 Unit & Integration Tests):

**API & Pipeline Tests (`test_api.py`)**:
- `test_health_check_endpoint`: Verifies `/api/health` reports DB, Redis, storage, and Gemini status.
- `test_upload_valid_audio`: Validates audio upload, storage persistence, and job queue dispatch.
- `test_upload_empty_file_rejected`: Confirms 0-byte uploads return HTTP 400.
- `test_upload_unsupported_file_format`: Confirms non-audio files (e.g. .pdf, .exe) return HTTP 400.
- `test_get_notes_list_and_sorting`: Confirms `/api/notes` returns records sorted newest first.
- `test_get_note_detail`: Validates full note payload with transcript and summary.
- `test_get_note_not_found`: Confirms non-existent IDs return HTTP 404.
- `test_status_endpoint`: Confirms lightweight polling format for frontend progress bars.
- `test_retry_failed_note`: Confirms `POST /api/notes/:id/retry` resets status to `QUEUED` and re-dispatches worker.
- `test_delete_note`: Confirms deletion removes both the DB record and object storage file.
- `test_worker_pipeline_success`: Validates end-to-end background transcription and summary generation.
- `test_worker_pipeline_transcription_failure`: Validates friendly error message recording on service timeout.

**Google Gemini Summarization Tests (`test_gemini_summary.py`)**:
- `test_gemini_empty_or_whitespace_transcript`: Verifies immediate graceful message without calling Gemini.
- `test_gemini_fallback_when_no_api_key`: Validates structured extractive fallback when API key is missing.
- `test_gemini_successful_summary`: Validates structured Markdown output (`## Overview`, `## Key Points`, `## Important Details`, `## Action Items`).
- `test_gemini_empty_response_raises_error`: Validates error handling when Gemini returns empty response.
- `test_gemini_auth_error_no_retry`: Confirms 401/403 errors raise `GeminiAuthError` immediately without retrying.
- `test_gemini_rate_limit_retry`: Confirms 429 rate limit triggers exponential backoff retries.
- `test_gemini_timeout_error`: Confirms timeouts trigger backoff and map to `GeminiTimeoutError`.
- `test_hierarchical_summarization_large_transcript`: Validates chunking and hierarchical synthesis for long transcripts (>15,000 words).
- `test_worker_preserves_transcript_on_gemini_failure`: **Crucial Guarantee**: Transcripts are persisted before Gemini is called; Gemini failures never wipe the transcript.
- `test_worker_skips_gnani_on_retry_when_transcript_exists`: Validates that re-processing skips Gnani STT and directly re-attempts Gemini summarization.

### Frontend Type Checking & Build:

```bash
cd frontend
npm run build
```

---

## API Endpoints

| Method | Endpoint | Description | Sample Response |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/notes/upload` | Upload audio file (Multipart) | `{"id": "...", "status": "QUEUED", "progress": 10}` |
| `GET` | `/api/notes` | List previous uploads (newest first) | `[{"id": "...", "file_name": "memo.mp3", "status": "COMPLETED"}]` |
| `GET` | `/api/notes/{id}` | Get full note details, transcript, & summary | `{"id": "...", "transcript": "...", "summary": "..."}` |
| `GET` | `/api/notes/{id}/status` | Lightweight status polling endpoint | `{"id": "...", "status": "TRANSCRIBING", "progress": 50}` |
| `POST` | `/api/notes/{id}/retry` | Re-queue a failed note | `{"id": "...", "status": "QUEUED", "message": "Re-queued"}` |
| `DELETE` | `/api/notes/{id}` | Delete note record and storage file | `{"success": true, "message": "Deleted"}` |
| `GET` | `/api/health` | Service health check | `{"status": "healthy", "database": "healthy", "redis": "connected"}` |

---

## Long Audio Processing

Gnani's REST STT endpoint imposes a strict 60-second audio duration ceiling (with an ideal duration of ≤ 30s). Recordings exceeding 60 seconds return an HTTP 400 error (`Audio duration exceeds maximum limit of 60 seconds`).

To comfortably handle recordings of **2 minutes, 10 minutes, or longer**, the Audio Notes Platform implements a dual-layer strategy:

1. **Gnani STT Batch Jobs API (`POST /stt/v3/batch/jobs`)**:
   - For long recordings (MP3, M4A, AAC, FLAC), the worker creates an asynchronous batch job on Gnani's infrastructure.
   - The worker calls `POST /stt/v3/batch/jobs/:id/start` and polls `GET /stt/v3/batch/jobs/:id` every 5 seconds.
   - Once completed, the worker retrieves the file transcript URL and downloads the full transcript.
   - Emits granular stage progress updates (`Transcribing batch audio (IN_PROGRESS)...`) so the UI stays active.

2. **Deterministic Wave Segment Chunking**:
   - For WAV recordings, pure Python `wave` chunking splits the audio into sequential 40-second chunks without requiring external binaries.
   - Each chunk is transcribed sequentially via the REST STT API with ITN enabled.
   - The worker calculates progress based on chunk index (e.g. `Transcribing segment 2 of 4 (52%)...`) and stitches the transcripts into a single unified output.

---

## Error Handling & Retries

The system categorizes and handles failures gracefully:

- **Upload Validation Failures**: Handled on both client and server (0-byte files, files > 100MB, unsupported extensions) with clear instructional messages.
- **Gnani Authentication Error (401/403)**: Non-retryable. Flagged with: *"We couldn't authenticate with the Gnani transcription service. Please verify server API configuration."*
- **Gnani Rate Limit (429)**: Retried automatically using exponential backoff ($1.5s \times 2^{attempt}$).
- **Gnani Server Error (500/502/503) & Timeouts**: Retried up to 3 times before setting status to `FAILED`.
- **User-Initiated Retries**: When a note fails, a prominent **Retry Processing** button appears on the UI, calling `POST /api/notes/:id/retry` to re-enqueue the job without forcing the user to re-upload the file.

---

## Design Decisions

1. **Why FastAPI?** High-performance asynchronous Python framework with native Pydantic schema validation, automatic OpenAPI interactive documentation (`/docs`), and lightweight memory footprint.
2. **Why Asynchronous Workers?** Audio transcription and LLM inference take seconds to minutes. Keeping them in the HTTP upload request causes gateway timeouts (e.g. Cloudflare 100s limit, Heroku 30s limit, Nginx proxy timeouts). Background jobs guarantee zero timeouts.
3. **Why S3-Compatible Object Storage?** Storing binary audio blobs inside PostgreSQL degrades database performance, bloats backups, and exhausts connection memory. Object storage is cheaper, infinitely scalable, and industry-standard.
4. **Why Fallback Thread Worker?** In production, Redis + RQ provides distributed, multi-worker scaling. For local evaluation, testing, or environments without Redis installed, the in-process daemon thread worker ensures the application runs out-of-the-box without extra infrastructure.
5. **Why Extractive Fallback Summarizer?** If an LLM API key is not configured or an external LLM quota is exhausted, the platform automatically generates structured notes directly from the transcript, ensuring the user experience never breaks.

---

## Future Improvements

- **Speaker Diarization**: Utilize Gnani's `with_diarization` feature to identify and label different speakers (Speaker 1, Speaker 2) in transcripts.
- **Realtime WebSockets / SSE**: Replace status polling with Server-Sent Events (SSE) or WebSockets for live word-by-word streaming.
- **Interactive Audio Waveform**: Embed an audio player with synchronized waveform scrubbing (e.g. Wavesurfer.js).
- **Multi-Tenant User Accounts**: Add authentication (Clerk / Supabase Auth) for individual private audio workspaces.

---

## License

MIT License. Developed for the Gnani Innovations Private Limited Take-Home Assessment.

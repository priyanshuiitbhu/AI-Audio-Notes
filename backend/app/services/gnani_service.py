import os
import time
import json
import logging
from typing import Optional, Callable, Dict, Any, List
import requests
from app.config import settings
from app.utils.audio_utils import split_wav_file, split_audio_file, cleanup_temp_files, get_audio_duration_seconds

logger = logging.getLogger(__name__)


class GnaniException(Exception):
    """Base exception for Gnani service."""
    pass


class GnaniAuthError(GnaniException):
    """Authentication or permission error (401, 403)."""
    pass


class GnaniRateLimitError(GnaniException):
    """Rate limit error (429)."""
    pass


class GnaniTimeoutError(GnaniException):
    """Timeout error communicating with Gnani API."""
    pass


class GnaniInvalidAudioError(GnaniException):
    """Invalid audio format or parameters (400)."""
    pass


class GnaniAPIError(GnaniException):
    """Gnani server or unknown error."""
    pass


class GnaniService:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.GNANI_API_KEY
        self.base_url = (base_url or settings.GNANI_API_BASE_URL).rstrip("/")

    def _get_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise GnaniAuthError("Gnani API key is not configured. Please set the GNANI_API_KEY environment variable.")
        return {
            "X-API-Key-ID": self.api_key
        }

    def transcribe_file_single(
        self,
        file_path: str,
        language_code: str = "en-IN",
        max_retries: int = 3,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """
        Transcribes a single audio file (<= 60s) via Gnani REST STT v3 endpoint.
        Implements retries with exponential backoff for transient errors.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        url = f"{self.base_url}/stt/v3"
        headers = self._get_headers()
        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
            ".aac": "audio/aac",
            ".m4a": "audio/m4a",
        }
        content_type = mime_map.get(ext, "audio/wav")

        attempt = 0
        backoff_seconds = 1.5

        while attempt < max_retries:
            attempt += 1
            try:
                logger.info(f"Sending audio to Gnani STT REST API (attempt {attempt}/{max_retries})")
                with open(file_path, "rb") as f:
                    files = {
                        "audio_file": (os.path.basename(file_path), f, content_type)
                    }
                    data = {
                        "language_code": language_code,
                        "format": "transcribe",
                    }
                    response = requests.post(url, headers=headers, files=files, data=data, timeout=timeout)

                # Check HTTP status
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success", False):
                        transcript = data.get("transcript", "").strip()
                        return {
                            "transcript": transcript,
                            "request_id": data.get("request_id"),
                            "model": data.get("model", "gnani-prisma-v2.5"),
                            "processing_time": data.get("processing_time"),
                        }
                    else:
                        error_detail = data.get("message") or data.get("error") or "Unknown API response"
                        raise GnaniAPIError(f"Gnani API returned failure: {error_detail}")

                elif response.status_code in (401, 403):
                    logger.error("Gnani authentication failure. Check GNANI_API_KEY.")
                    raise GnaniAuthError("Authentication failed with Gnani ASR API. Please verify your API key.")

                elif response.status_code == 400:
                    try:
                        err_json = response.json()
                        err_msg = err_json.get("error", {}).get("message") or err_json.get("message") or response.text
                    except Exception:
                        err_msg = response.text
                    logger.error(f"Gnani 400 Bad Request: {err_msg}")
                    raise GnaniInvalidAudioError(f"Gnani rejected audio format: {err_msg}")

                elif response.status_code == 429:
                    logger.warning(f"Gnani rate limit reached (attempt {attempt}). Backing off...")
                    if attempt >= max_retries:
                        raise GnaniRateLimitError("Gnani API rate limit reached. Please retry in a few moments.")
                    time.sleep(backoff_seconds * (2 ** (attempt - 1)))
                    continue

                elif response.status_code in (500, 502, 503, 504):
                    logger.warning(f"Gnani server error {response.status_code} (attempt {attempt})")
                    if attempt >= max_retries:
                        raise GnaniAPIError(f"Gnani server temporarily unavailable (status {response.status_code}).")
                    time.sleep(backoff_seconds * (2 ** (attempt - 1)))
                    continue

                else:
                    raise GnaniAPIError(f"Gnani API error (status {response.status_code}): {response.text[:200]}")

            except requests.exceptions.Timeout:
                logger.warning(f"Gnani request timed out (attempt {attempt})")
                if attempt >= max_retries:
                    raise GnaniTimeoutError("Connection to Gnani transcription service timed out. Please retry.")
                time.sleep(backoff_seconds)
            except (GnaniAuthError, GnaniInvalidAudioError):
                raise
            except requests.exceptions.RequestException as e:
                logger.warning(f"Network error calling Gnani (attempt {attempt}): {e}")
                if attempt >= max_retries:
                    raise GnaniAPIError(f"Network error communicating with Gnani STT API: {str(e)}")
                time.sleep(backoff_seconds)

        raise GnaniAPIError("Gnani transcription failed after maximum retries.")

    def transcribe_batch_long_audio(
        self,
        file_path: str,
        language_code: str = "en-IN",
        progress_callback: Optional[Callable[[int, str], None]] = None,
        poll_interval: int = 5,
        max_poll_time: int = 300,
    ) -> Dict[str, Any]:
        """
        Transcribes long audio files (> 60s) via Gnani STT Batch Jobs API.
        Flow:
        1. POST /stt/v3/batch/jobs (Upload & create job)
        2. POST /stt/v3/batch/jobs/{id}/start (Start job)
        3. Poll GET /stt/v3/batch/jobs/{id} until COMPLETED
        4. GET /stt/v3/batch/jobs/{id}/files?status=COMPLETED
        5. Download transcript JSON
        """
        url_create = f"{self.base_url}/stt/v3/batch/jobs"
        headers = self._get_headers()
        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
            ".aac": "audio/aac",
            ".m4a": "audio/m4a",
        }
        content_type = mime_map.get(ext, "audio/wav")

        logger.info(f"Submitting long audio to Gnani STT Batch API: {file_path}")
        if progress_callback:
            progress_callback(35, "Creating batch transcription job...")

        # 1. Create Job
        with open(file_path, "rb") as f:
            files = {
                "files": (os.path.basename(file_path), f, content_type)
            }
            data = {
                "config": json.dumps({
                    "model": "gnani-prisma-v2.5",
                    "language_code": language_code,
                    "mode": "transcribe"
                })
            }
            create_resp = requests.post(url_create, headers=headers, files=files, data=data, timeout=60)

        if create_resp.status_code not in (200, 201):
            raise GnaniAPIError(f"Failed to create Batch STT job ({create_resp.status_code}): {create_resp.text[:300]}")

        job_data = create_resp.json()
        job_id = job_data.get("job_id")
        if not job_id:
            raise GnaniAPIError("Batch job creation did not return job_id")

        logger.info(f"Gnani Batch Job created with ID: {job_id}")

        # 2. Start Job
        if progress_callback:
            progress_callback(40, "Starting batch transcription job...")

        url_start = f"{self.base_url}/stt/v3/batch/jobs/{job_id}/start"
        start_resp = requests.post(url_start, headers=headers, timeout=30)
        if start_resp.status_code not in (200, 202):
            raise GnaniAPIError(f"Failed to start Batch STT job ({start_resp.status_code}): {start_resp.text[:300]}")

        # 3. Poll Status
        start_time = time.time()
        url_status = f"{self.base_url}/stt/v3/batch/jobs/{job_id}"
        poll_count = 0

        while (time.time() - start_time) < max_poll_time:
            poll_count += 1
            time.sleep(poll_interval)
            status_resp = requests.get(url_status, headers=headers, timeout=30)
            if status_resp.status_code != 200:
                logger.warning(f"Batch poll status check returned {status_resp.status_code}")
                continue

            status_info = status_resp.json()
            status = status_info.get("status", "").upper()
            logger.info(f"Gnani Batch Job {job_id} status: {status}")

            if progress_callback:
                # Progress scale 40 to 65 during batch polling
                calc_progress = min(65, 40 + poll_count * 3)
                progress_callback(calc_progress, f"Transcribing batch audio ({status})...")

            if status == "COMPLETED":
                break
            elif status in ("FAILED", "CANCELLED", "ERROR"):
                error_msg = status_info.get("message") or "Batch job marked failed"
                raise GnaniAPIError(f"Gnani Batch Job failed: {error_msg}")

        # 4. Get completed file transcript URL
        url_files = f"{self.base_url}/stt/v3/batch/jobs/{job_id}/files?status=COMPLETED"
        files_resp = requests.get(url_files, headers=headers, timeout=30)
        if files_resp.status_code != 200:
            raise GnaniAPIError(f"Failed to retrieve batch job files: {files_resp.text[:200]}")

        files_data = files_resp.json()
        file_list = files_data.get("files") or files_data.get("results") or []
        if not file_list and isinstance(files_data, list):
            file_list = files_data

        if not file_list:
            raise GnaniAPIError("Gnani Batch job completed but returned no files.")

        first_file = file_list[0]
        transcript_url = first_file.get("transcript_url")
        if transcript_url:
            # 5. Fetch full transcript
            tr_resp = requests.get(transcript_url, timeout=30)
            if tr_resp.status_code == 200:
                tr_json = tr_resp.json()
                return {
                    "transcript": tr_json.get("full_transcript") or tr_json.get("transcript", ""),
                    "request_id": job_id,
                    "model": tr_json.get("model", "gnani-prisma-v2.5"),
                    "duration": tr_json.get("duration_seconds"),
                }

        # Fallback if transcript was inline
        if "transcript" in first_file or "full_transcript" in first_file:
            return {
                "transcript": first_file.get("full_transcript") or first_file.get("transcript", ""),
                "request_id": job_id,
                "model": "gnani-prisma-v2.5",
            }

        raise GnaniAPIError("Could not extract transcript from Batch STT output.")

    def transcribe(
        self,
        file_path: str,
        language_code: str = "en-IN",
        progress_callback: Optional[Callable[[int, str], None]] = None,
        note_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Unified transcription handler:
        - For audio <= 28 seconds: routes to direct Gnani STT REST API (strict Gnani limit is 30s).
        - For audio > 28 seconds (or if single REST throws duration-limit error):
          Splits into safe ordered PCM chunks (<= 24s each), transcribes each chunk
          sequentially with real-time per-chunk progress reporting, and recombines the full transcript.
        """
        max_single_duration = 28.0
        chunk_duration_sec = 24
        log_prefix = f"[note_id={note_id}] " if note_id else ""

        duration = get_audio_duration_seconds(file_path)
        logger.info(f"{log_prefix}Audio file: {file_path}, detected duration: {duration}s")

        # 1. Short audio routing (<= 28s)
        if duration is not None and duration <= max_single_duration:
            logger.info(f"{log_prefix}Audio duration: {duration:.2f}s <= {max_single_duration}s threshold.")
            logger.info(f"{log_prefix}Processing strategy: NORMAL_STT")
            if progress_callback:
                progress_callback(40, "Transcribing audio with Gnani ASR...")
            try:
                result = self.transcribe_file_single(file_path, language_code=language_code)
                result["duration"] = duration
                return result
            except GnaniInvalidAudioError as e:
                err_lower = str(e).lower()
                if "exceeds maximum allowed duration" in err_lower or "30 seconds" in err_lower or "duration" in err_lower:
                    logger.warning(f"{log_prefix}Normal STT rejected audio for duration: {e}. Re-routing to CHUNKED_STT strategy.")
                else:
                    raise
            except Exception:
                raise

        # 2. Long audio routing (> 28s or fallback)
        dur_str = f"{duration:.2f}s" if duration is not None else "unknown"
        logger.info(f"{log_prefix}Audio duration: {dur_str} > {max_single_duration}s.")
        logger.info(f"{log_prefix}Processing strategy: CHUNKED_STT")

        chunks, temp_cleanup = split_audio_file(file_path, chunk_duration_sec=chunk_duration_sec)
        total_chunks = len(chunks)

        if total_chunks <= 1 and duration is not None and duration <= max_single_duration:
            if progress_callback:
                progress_callback(40, "Transcribing audio with Gnani ASR...")
            result = self.transcribe_file_single(file_path, language_code=language_code)
            result["duration"] = duration
            return result

        logger.info(f"{log_prefix}Splitting complete: {total_chunks} chunks of ~{chunk_duration_sec}s each")
        transcripts: List[str] = []

        try:
            for idx, chunk in enumerate(chunks):
                chunk_num = idx + 1
                # Real progress tracking: maps 25% to 70% across chunks
                pct = int(25 + (chunk_num / total_chunks) * 45)
                stage_desc = f"Transcribing segment {chunk_num} of {total_chunks}..."
                logger.info(f"{log_prefix}Chunk {chunk_num}/{total_chunks}: {stage_desc}")
                if progress_callback:
                    progress_callback(pct, stage_desc)

                chunk_res = self.transcribe_file_single(chunk, language_code=language_code)
                chunk_text = chunk_res.get("transcript", "").strip()
                if chunk_text:
                    transcripts.append(chunk_text)
                logger.info(f"{log_prefix}Chunk {chunk_num}/{total_chunks} transcribed successfully ({len(chunk_text)} chars)")
        finally:
            cleanup_temp_files(temp_cleanup)
            cleanup_temp_files(chunks)

        full_transcript = " ".join(transcripts).strip()
        logger.info(f"{log_prefix}All {total_chunks} chunks transcribed. Combined transcript length: {len(full_transcript)} chars.")

        return {
            "transcript": full_transcript,
            "request_id": f"chunked_{total_chunks}",
            "model": "gnani-prisma-v2.5",
            "duration": duration,
            "chunk_count": total_chunks,
        }


gnani_service = GnaniService()

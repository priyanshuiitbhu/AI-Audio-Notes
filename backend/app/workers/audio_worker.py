import os
import tempfile
import logging
from datetime import datetime, timezone
from app.database import SessionLocal
from app.models.note import Note, NoteStatus, get_utc_now
from app.services.storage_service import storage_service
from app.services.gnani_service import (
    gnani_service,
    GnaniAuthError,
    GnaniRateLimitError,
    GnaniTimeoutError,
    GnaniInvalidAudioError,
    GnaniAPIError,
)
from app.services.summary_service import (
    summary_service,
    GeminiAuthError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiError,
)
from app.utils.audio_utils import get_audio_duration_seconds

logger = logging.getLogger(__name__)


def process_audio_note(note_id: str):
    """
    Background worker pipeline:
    1. Check if transcript already exists (e.g. from retry where only summarization failed).
    2. If not, fetch audio from storage and transcribe via Gnani ASR API.
    3. Save transcript to PostgreSQL and update status to SUMMARIZING.
    4. Call Google Gemini to generate structured executive notes.
    5. Save summary and mark note as COMPLETED.
    6. Catch errors gracefully: if Gemini fails, transcript remains saved!
    """
    db = SessionLocal()
    is_temp_file = False
    local_path = None

    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            logger.error(f"[note_id={note_id}] Note record not found in database.")
            return

        logger.info(f"[note_id={note_id}] Starting audio processing for '{note.file_name}'")

        transcript = note.transcript.strip() if note.transcript else ""

        # Step 1: If transcript does not already exist, perform Gnani Speech-to-Text
        if not transcript:
            note.status = NoteStatus.PROCESSING.value
            note.progress = 15
            note.current_stage = "Preparing audio file..."
            db.commit()

            try:
                local_path = storage_service.get_local_file_path(note.storage_key)
                temp_root = os.path.realpath(tempfile.gettempdir())
                resolved_path = os.path.realpath(local_path)
                is_temp_file = os.path.commonpath([temp_root, resolved_path]) == temp_root
            except Exception as e:
                logger.error(f"[note_id={note_id}] Failed to retrieve file from storage: {e}")
                raise RuntimeError(f"Storage retrieval failed: {str(e)}")

            duration = get_audio_duration_seconds(local_path)
            if duration:
                note.duration_seconds = round(duration, 2)
                db.commit()

            note.status = NoteStatus.TRANSCRIBING.value
            note.progress = 30
            note.current_stage = "Initiating Gnani transcription..."
            db.commit()

            def update_transcription_progress(pct: int, stage_desc: str):
                try:
                    db_refresh = SessionLocal()
                    n = db_refresh.query(Note).filter(Note.id == note_id).first()
                    if n:
                        n.progress = pct
                        n.current_stage = stage_desc
                        db_refresh.commit()
                    db_refresh.close()
                except Exception as pe:
                    logger.debug(f"[note_id={note_id}] Progress update error: {pe}")

            if note.duration_seconds:
                logger.info(f"[note_id={note_id}] Audio duration: {note.duration_seconds} seconds")

            logger.info(f"[note_id={note_id}] Calling Gnani STT service...")
            try:
                asr_result = gnani_service.transcribe(
                    file_path=local_path,
                    language_code=note.language_code,
                    progress_callback=update_transcription_progress,
                    note_id=note_id,
                )
                transcript = asr_result.get("transcript", "").strip()
                if not note.duration_seconds and asr_result.get("duration"):
                    note.duration_seconds = round(asr_result["duration"], 2)
                    db.commit()
            except GnaniAuthError as e:
                logger.error(f"[note_id={note_id}] Gnani authentication error: {e}")
                _fail_note(db, note_id, "Transcription failed. We couldn't authenticate with the Gnani transcription service. Please verify server API configuration.")
                return
            except GnaniRateLimitError as e:
                logger.error(f"[note_id={note_id}] Gnani rate limit error: {e}")
                _fail_note(db, note_id, "Transcription failed. The transcription service is currently experiencing high load. Please retry in a few moments.")
                return
            except GnaniTimeoutError as e:
                logger.error(f"[note_id={note_id}] Gnani timeout: {e}")
                _fail_note(db, note_id, "Transcription failed. The transcription service timed out. Please try again.")
                return
            except GnaniInvalidAudioError as e:
                logger.error(f"[note_id={note_id}] Invalid audio: {e}")
                _fail_note(db, note_id, f"Transcription failed. The audio file could not be recognized: {str(e)}")
                return
            except Exception as e:
                logger.exception(f"[note_id={note_id}] Unexpected error during transcription: {e}")
                _fail_note(db, note_id, "Transcription failed. We couldn't process this audio.")
                return

            # Save transcript immediately to PostgreSQL
            note.transcript = transcript
            db.commit()
            logger.info(f"[note_id={note_id}] Transcript saved to database ({len(transcript)} chars).")

        else:
            logger.info(f"[note_id={note_id}] Using existing transcript ({len(transcript)} chars), skipping re-transcription.")

        # Step 2: Transition to SUMMARIZING stage
        note.status = NoteStatus.SUMMARIZING.value
        note.progress = 75
        note.current_stage = "Generating summary with Google Gemini..."
        db.commit()

        # Step 3: Google Gemini Summarization
        logger.info(f"[note_id={note_id}] Prompting Google Gemini ({summary_service.model_name})")
        try:
            summary_text = summary_service.generate_summary(transcript)
            note.summary = summary_text
            note.progress = 100
            note.current_stage = "Completed"
            note.status = NoteStatus.COMPLETED.value
            note.completed_at = get_utc_now()
            note.error_message = None
            db.commit()
            logger.info(f"[note_id={note_id}] Processing pipeline COMPLETED successfully with Google Gemini.")

        except GeminiAuthError as ge:
            logger.error(f"[note_id={note_id}] Gemini authentication error: {ge}")
            _fail_note(db, note_id, "Transcript generated successfully, but summary generation failed due to an authentication error. The transcript is still available.")
        except GeminiRateLimitError as ge:
            logger.error(f"[note_id={note_id}] Gemini rate limit error: {ge}")
            _fail_note(db, note_id, "Transcript generated successfully, but summary generation failed because Gemini rate limit was reached. The transcript is still available.")
        except GeminiTimeoutError as ge:
            logger.error(f"[note_id={note_id}] Gemini timeout error: {ge}")
            _fail_note(db, note_id, "Transcript generated successfully, but summary generation timed out. The transcript is still available.")
        except Exception as ge:
            logger.error(f"[note_id={note_id}] Gemini summarization error: {ge}")
            _fail_note(db, note_id, "Transcript generated successfully, but summary generation failed. The transcript is still available.")

    except Exception as e:
        logger.exception(f"[note_id={note_id}] Top-level worker exception: {e}")
        _fail_note(db, note_id, f"An unexpected error occurred while processing: {str(e)}")

    finally:
        if is_temp_file and local_path and os.path.isfile(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass
        db.close()


def _fail_note(db, note_id: str, human_readable_error: str):
    """
    Sets status to FAILED and stores human-readable error.
    CRITICAL: Does NOT erase or clear note.transcript!
    """
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if note:
            note.status = NoteStatus.FAILED.value
            note.error_message = human_readable_error
            note.current_stage = f"Failed: {human_readable_error}"
            db.commit()
    except Exception as dbe:
        logger.error(f"[note_id={note_id}] Failed to set error status: {dbe}")

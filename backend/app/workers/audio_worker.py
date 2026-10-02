import os
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
from app.services.summary_service import summary_service
from app.utils.audio_utils import get_audio_duration_seconds

logger = logging.getLogger(__name__)


def process_audio_note(note_id: str):
    """
    Background worker task to process an uploaded audio note:
    1. Retrieve audio file from storage
    2. Transcribe via Gnani STT API (with stage and progress updates)
    3. Save transcript to PostgreSQL
    4. Generate summary via LLM
    5. Save summary and mark note as COMPLETED
    6. Catch errors gracefully and record human-readable error messages
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

        # Step 1: Mark as PROCESSING
        note.status = NoteStatus.PROCESSING.value
        note.progress = 15
        note.current_stage = "Preparing audio file..."
        db.commit()

        # Step 2: Retrieve audio file from storage
        try:
            local_path = storage_service.get_local_file_path(note.storage_key)
            if "/tmp/" in local_path or "NamedTemporaryFile" in local_path:
                is_temp_file = True
        except Exception as e:
            logger.error(f"[note_id={note_id}] Failed to retrieve file from storage: {e}")
            raise RuntimeError(f"Storage retrieval failed: {str(e)}")

        # Detect duration
        duration = get_audio_duration_seconds(local_path)
        if duration:
            note.duration_seconds = round(duration, 2)
            db.commit()

        # Step 3: Transcription with Gnani
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

        logger.info(f"[note_id={note_id}] Calling Gnani STT API (duration: {note.duration_seconds}s)")
        asr_result = gnani_service.transcribe(
            file_path=local_path,
            language_code=note.language_code,
            progress_callback=update_transcription_progress,
        )

        transcript = asr_result.get("transcript", "").strip()
        note.transcript = transcript
        note.progress = 75
        note.current_stage = "Transcript generated. Generating summary..."
        note.status = NoteStatus.SUMMARIZING.value
        db.commit()
        logger.info(f"[note_id={note_id}] Transcription completed successfully. Transcript length: {len(transcript)} chars.")

        # Step 4: LLM Summarization
        logger.info(f"[note_id={note_id}] Generating summary via LLM service")
        summary_text = summary_service.summarize(transcript)
        note.summary = summary_text
        note.progress = 100
        note.current_stage = "Completed"
        note.status = NoteStatus.COMPLETED.value
        note.completed_at = get_utc_now()
        note.error_message = None
        db.commit()
        logger.info(f"[note_id={note_id}] Processing pipeline COMPLETED successfully.")

    except GnaniAuthError as e:
        logger.error(f"[note_id={note_id}] Gnani authentication error: {e}")
        _fail_note(db, note_id, "We couldn't authenticate with the Gnani transcription service. Please verify server API configuration.")
    except GnaniRateLimitError as e:
        logger.error(f"[note_id={note_id}] Gnani rate limit error: {e}")
        _fail_note(db, note_id, "The transcription service is currently experiencing high load. Please retry in a few moments.")
    except GnaniTimeoutError as e:
        logger.error(f"[note_id={note_id}] Gnani timeout: {e}")
        _fail_note(db, note_id, "We couldn't transcribe this audio because the transcription service timed out. Please try again.")
    except GnaniInvalidAudioError as e:
        logger.error(f"[note_id={note_id}] Invalid audio: {e}")
        _fail_note(db, note_id, f"The audio file could not be recognized by the speech engine: {str(e)}")
    except Exception as e:
        logger.exception(f"[note_id={note_id}] Unexpected error during processing: {e}")
        _fail_note(db, note_id, f"An error occurred while processing the audio note: {str(e)}")

    finally:
        # Cleanup temporary file if downloaded from cloud storage
        if is_temp_file and local_path and os.path.isfile(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass
        db.close()


def _fail_note(db, note_id: str, human_readable_error: str):
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if note:
            note.status = NoteStatus.FAILED.value
            note.error_message = human_readable_error
            note.current_stage = f"Failed: {human_readable_error}"
            db.commit()
    except Exception as dbe:
        logger.error(f"[note_id={note_id}] Failed to set error status: {dbe}")

import os
import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.note import Note, NoteStatus, get_utc_now
from app.schemas.note import (
    NoteUploadResponse,
    NoteStatusResponse,
    NoteListItemResponse,
    NoteDetailResponse,
    NoteRetryResponse,
)
from app.services.storage_service import storage_service
from app.services.job_service import enqueue_audio_job
from app.utils.audio_utils import validate_audio_file, sanitize_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notes", tags=["Notes"])


@router.post("/upload", response_model=NoteUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_audio_note(
    file: UploadFile = File(...),
    language_code: str = Form("en-IN"),
    db: Session = Depends(get_db),
):
    """
    Synchronous Upload Endpoint:
    1. Validates audio file size and format.
    2. Uploads file to object storage under safe key.
    3. Creates database record in QUEUED state.
    4. Enqueues background job.
    5. Returns note ID immediately.
    """
    raw_filename = file.filename or "unnamed_audio.wav"
    clean_filename = sanitize_filename(raw_filename)

    # Read audio bytes
    try:
        content = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read the uploaded audio file."
        )

    file_size = len(content)

    # Validate file
    is_valid, error_msg = validate_audio_file(
        clean_filename,
        file_size,
        content_type=file.content_type
    )
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Generate note ID
    note_id = str(uuid.uuid4())

    # Save to storage
    try:
        storage_key = storage_service.save_file(note_id, clean_filename, content)
    except Exception as e:
        logger.error(f"Storage upload failed for note {note_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist audio file to storage."
        )

    # Create DB record
    note = Note(
        id=note_id,
        file_name=clean_filename,
        storage_key=storage_key,
        file_size=file_size,
        mime_type=file.content_type or "audio/wav",
        language_code=language_code,
        status=NoteStatus.QUEUED.value,
        progress=10,
        current_stage="Queued in processing pipeline",
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    # Enqueue background job
    enqueue_audio_job(note.id)

    logger.info(f"Note {note.id} created and queued successfully.")
    return NoteUploadResponse(
        id=note.id,
        file_name=note.file_name,
        status=note.status,
        progress=note.progress,
        current_stage=note.current_stage,
        message="Audio uploaded successfully and queued for transcription and AI summarization."
    )


@router.get("", response_model=List[NoteListItemResponse])
def list_notes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Returns previous note uploads, sorted newest first.
    """
    notes = db.query(Note).order_by(Note.created_at.desc()).offset(skip).limit(limit).all()
    results = []
    for n in notes:
        preview = None
        if n.summary:
            # First 150 characters
            preview = n.summary.replace("#", "").replace("*", "").strip()[:140]
            if len(n.summary) > 140:
                preview += "..."

        results.append(
            NoteListItemResponse(
                id=n.id,
                file_name=n.file_name,
                file_size=n.file_size,
                mime_type=n.mime_type,
                duration_seconds=n.duration_seconds,
                status=n.status,
                progress=n.progress,
                current_stage=n.current_stage,
                summary_preview=preview,
                created_at=n.created_at,
                completed_at=n.completed_at,
            )
        )
    return results


@router.get("/{note_id}", response_model=NoteDetailResponse)
def get_note_detail(
    note_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieves complete details of a specific note by ID.
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.get("/{note_id}/status", response_model=NoteStatusResponse)
def get_note_status(
    note_id: str,
    db: Session = Depends(get_db),
):
    """
    Lightweight polling endpoint to monitor processing status.
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    return NoteStatusResponse(
        id=note.id,
        status=note.status,
        progress=note.progress,
        current_stage=note.current_stage,
        error_message=note.error_message,
        has_transcript=bool(note.transcript and note.transcript.strip()),
        completed_at=note.completed_at,
    )


@router.get("/{note_id}/audio")
def get_note_audio(
    note_id: str,
    db: Session = Depends(get_db),
):
    """
    Streams original audio recording securely without exposing storage credentials.
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    try:
        local_path = storage_service.get_local_file_path(note.storage_key)
        if local_path and os.path.isfile(local_path):
            return FileResponse(
                path=local_path,
                media_type=note.mime_type or "audio/wav",
                filename=note.file_name,
            )
    except Exception:
        pass

    try:
        content = storage_service.get_file_bytes(note.storage_key)
        return Response(
            content=content,
            media_type=note.mime_type or "audio/wav",
            headers={"Content-Disposition": f'inline; filename="{note.file_name}"'},
        )
    except Exception as e:
        logger.error(f"Failed to fetch audio for note {note_id}: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found in storage.")


@router.post("/{note_id}/retry", response_model=NoteRetryResponse)
def retry_note(
    note_id: str,
    db: Session = Depends(get_db),
):
    """
    Requeues a failed note for reprocessing.
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if note.status not in (NoteStatus.FAILED.value, NoteStatus.COMPLETED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Note is currently in {note.status} state and cannot be retried."
        )

    note.status = NoteStatus.QUEUED.value
    note.progress = 10
    note.current_stage = "Re-queued for processing"
    note.error_message = None
    note.retry_count += 1
    db.commit()

    enqueue_audio_job(note.id)
    logger.info(f"Note {note_id} re-queued (retry count: {note.retry_count})")

    return NoteRetryResponse(
        id=note.id,
        status=note.status,
        message="Job successfully re-queued for processing."
    )


@router.delete("/{note_id}")
def delete_note(
    note_id: str,
    db: Session = Depends(get_db),
):
    """
    Deletes a note record and its audio storage file.
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    # Delete storage file
    try:
        storage_service.delete_file(note.storage_key)
    except Exception as e:
        logger.warning(f"Failed to delete storage file {note.storage_key}: {e}")

    db.delete(note)
    db.commit()
    logger.info(f"Deleted note {note_id}")
    return {"success": True, "message": "Note deleted successfully."}

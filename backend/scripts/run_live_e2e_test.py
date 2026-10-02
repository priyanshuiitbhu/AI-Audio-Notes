import os
import sys
import time
from app.database import SessionLocal, init_db
from app.models.note import Note, NoteStatus
from app.services.storage_service import storage_service
from app.workers.audio_worker import process_audio_note
from app.config import settings

def main():
    print("=" * 60)
    print("STARTING LIVE E2E PIPELINE TEST (GNANI ASR + GOOGLE GEMINI)")
    print("=" * 60)

    print(f"Gnani configured: {bool(settings.GNANI_API_KEY)}")
    print(f"Gemini configured: {bool(settings.GEMINI_API_KEY)}")
    print(f"Gemini model: {settings.GEMINI_MODEL}")

    init_db()
    source_wav = "storage/audio/71621175-4499-474b-b78b-209d8401c195/meeting_notes.wav"
    if not os.path.exists(source_wav):
        print(f"Source file not found: {source_wav}")
        sys.exit(1)

    with open(source_wav, "rb") as f:
        audio_bytes = f.read()

    note_id = "live-e2e-gemini-test"
    db = SessionLocal()

    # Clean up prior test if exists
    prior = db.query(Note).filter(Note.id == note_id).first()
    if prior:
        db.delete(prior)
        db.commit()

    storage_key = storage_service.save_file(note_id, "meeting_notes.wav", audio_bytes)
    print(f"Audio saved to storage: {storage_key} ({len(audio_bytes)} bytes)")

    note = Note(
        id=note_id,
        file_name="meeting_notes.wav",
        storage_key=storage_key,
        file_size=len(audio_bytes),
        mime_type="audio/wav",
        language_code="en-IN",
        status=NoteStatus.QUEUED.value,
        progress=10,
        current_stage="Queued",
    )
    db.add(note)
    db.commit()
    db.close()

    print(f"Triggering background worker for note_id: {note_id}...")
    start_time = time.time()
    process_audio_note(note_id)
    duration = time.time() - start_time
    print(f"Worker completed execution in {duration:.2f}s")

    # Fetch result from DB
    db = SessionLocal()
    result_note = db.query(Note).filter(Note.id == note_id).first()

    print("\n--- TEST RESULTS ---")
    print(f"Status: {result_note.status}")
    print(f"Progress: {result_note.progress}%")
    print(f"Stage: {result_note.current_stage}")
    print(f"Error Message: {result_note.error_message}")
    print(f"\n--- GNANI TRANSCRIPT ({len(result_note.transcript or '')} chars) ---")
    print(result_note.transcript)
    print(f"\n--- GEMINI SUMMARY ({len(result_note.summary or '')} chars) ---")
    print(result_note.summary)

    assert result_note.status == NoteStatus.COMPLETED.value, f"Expected COMPLETED, got {result_note.status}"
    assert result_note.transcript and len(result_note.transcript) > 0, "Expected non-empty transcript"
    assert result_note.summary and len(result_note.summary) > 0, "Expected non-empty summary"
    assert "Overview" in result_note.summary, "Expected 'Overview' in summary"
    assert "Key Points" in result_note.summary, "Expected 'Key Points' in summary"

    print("\n" + "=" * 60)
    print("SUCCESS: Full E2E Pipeline (Gnani ASR -> Transcript -> Google Gemini -> Summary) verified!")
    print("=" * 60)
    db.close()

if __name__ == "__main__":
    main()

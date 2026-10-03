import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models.note import Note, NoteStatus
from app.services.gnani_service import GnaniAuthError, GnaniTimeoutError, GnaniAPIError
from app.workers.audio_worker import process_audio_note

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=engine)
    yield
    # Clean up notes table after each test
    db = SessionLocal()
    db.query(Note).delete()
    db.commit()
    db.close()


def test_health_check_endpoint():
    """Verify GET /api/health returns 200 with service statuses."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "redis" in data
    assert "worker" in data
    assert "storage" in data
    assert "timestamp" in data


def test_upload_valid_audio():
    """Verify POST /api/notes/upload accepts valid audio and queues note."""
    audio_content = b"RIFF....WAVEfmt ...." + b"\x00" * 2000
    files = {
        "file": ("test_sample.wav", io.BytesIO(audio_content), "audio/wav")
    }

    with patch("app.api.notes.enqueue_audio_job") as mock_enqueue:
        response = client.post("/api/notes/upload", files=files, data={"language_code": "en-IN"})
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["file_name"] == "test_sample.wav"
        assert data["status"] == "QUEUED"
        assert data["progress"] == 10
        mock_enqueue.assert_called_once_with(data["id"])


def test_upload_empty_file_rejected():
    """Verify empty file is rejected with 400 error."""
    files = {
        "file": ("empty.wav", io.BytesIO(b""), "audio/wav")
    }
    response = client.post("/api/notes/upload", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_reports_queue_unavailable():
    """Production-style queue failures must be visible instead of silently losing work."""
    audio_content = b"RIFF....WAVEfmt ...." + b"\x00" * 2000
    files = {"file": ("queue_test.wav", io.BytesIO(audio_content), "audio/wav")}

    with patch("app.api.notes.enqueue_audio_job", return_value=False):
        response = client.post("/api/notes/upload", files=files, data={"language_code": "en-IN"})

    assert response.status_code == 503
    assert "queue" in response.json()["detail"].lower()


def test_upload_unsupported_file_format():
    """Verify unsupported file format (e.g. .pdf or .exe) is rejected."""
    files = {
        "file": ("document.pdf", io.BytesIO(b"%PDF-1.4 sample content"), "application/pdf")
    }
    response = client.post("/api/notes/upload", files=files)
    assert response.status_code == 400
    assert "unsupported audio format" in response.json()["detail"].lower()


def test_get_notes_list_and_sorting():
    """Verify GET /api/notes returns list sorted newest first."""
    db = SessionLocal()
    n1 = Note(
        id="note-1",
        file_name="first.wav",
        storage_key="audio/note-1/first.wav",
        file_size=1024,
        mime_type="audio/wav",
        status=NoteStatus.COMPLETED.value,
        progress=100,
        current_stage="Completed",
        summary="First meeting summary overview.",
    )
    n2 = Note(
        id="note-2",
        file_name="second.wav",
        storage_key="audio/note-2/second.wav",
        file_size=2048,
        mime_type="audio/wav",
        status=NoteStatus.QUEUED.value,
        progress=10,
        current_stage="Queued",
    )
    db.add(n1)
    db.add(n2)
    db.commit()
    db.close()

    response = client.get("/api/notes")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    assert items[0]["id"] == "note-2"  # Newest first
    assert items[1]["id"] == "note-1"
    assert items[1]["summary_preview"] is not None


def test_get_note_detail():
    """Verify GET /api/notes/{id} returns full details."""
    db = SessionLocal()
    n = Note(
        id="test-detail-id",
        file_name="meeting.mp3",
        storage_key="audio/test/meeting.mp3",
        file_size=5000,
        mime_type="audio/mpeg",
        status=NoteStatus.COMPLETED.value,
        progress=100,
        current_stage="Completed",
        transcript="This is the full transcribed text from the audio.",
        summary="### Overview\nKey summary notes.",
    )
    db.add(n)
    db.commit()
    db.close()

    response = client.get("/api/notes/test-detail-id")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-detail-id"
    assert data["transcript"] == "This is the full transcribed text from the audio."
    assert data["summary"] == "### Overview\nKey summary notes."


def test_get_note_not_found():
    """Verify 404 is returned for non-existent note ID."""
    response = client.get("/api/notes/non-existent-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Note not found"


def test_status_endpoint():
    """Verify GET /api/notes/{id}/status polling response."""
    db = SessionLocal()
    n = Note(
        id="poll-id",
        file_name="audio.wav",
        storage_key="audio/poll/audio.wav",
        file_size=2000,
        mime_type="audio/wav",
        status=NoteStatus.TRANSCRIBING.value,
        progress=50,
        current_stage="Transcribing segment 2 of 4...",
    )
    db.add(n)
    db.commit()
    db.close()

    response = client.get("/api/notes/poll-id/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "TRANSCRIBING"
    assert data["progress"] == 50
    assert data["current_stage"] == "Transcribing segment 2 of 4..."


def test_retry_failed_note():
    """Verify POST /api/notes/{id}/retry requeues failed notes."""
    db = SessionLocal()
    n = Note(
        id="retry-id",
        file_name="failed.wav",
        storage_key="audio/retry/failed.wav",
        file_size=2000,
        mime_type="audio/wav",
        status=NoteStatus.FAILED.value,
        progress=30,
        current_stage="Failed",
        error_message="Network timeout",
    )
    db.add(n)
    db.commit()
    db.close()

    with patch("app.api.notes.enqueue_audio_job") as mock_enqueue:
        response = client.post("/api/notes/retry-id/retry")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "QUEUED"
        mock_enqueue.assert_called_once_with("retry-id")

        # Verify DB updated
        db = SessionLocal()
        refreshed = db.query(Note).filter(Note.id == "retry-id").first()
        assert refreshed.status == "QUEUED"
        assert refreshed.error_message is None
        assert refreshed.retry_count == 1
        db.close()


def test_delete_note():
    """Verify DELETE /api/notes/{id} deletes note and storage file."""
    db = SessionLocal()
    n = Note(
        id="delete-id",
        file_name="audio.wav",
        storage_key="audio/delete/audio.wav",
        file_size=1000,
        mime_type="audio/wav",
        status=NoteStatus.COMPLETED.value,
        progress=100,
        current_stage="Completed",
    )
    db.add(n)
    db.commit()
    db.close()

    with patch("app.api.notes.storage_service.delete_file") as mock_del:
        mock_del.return_value = True
        response = client.delete("/api/notes/delete-id")
        assert response.status_code == 200
        mock_del.assert_called_once_with("audio/delete/audio.wav")

        db = SessionLocal()
        deleted = db.query(Note).filter(Note.id == "delete-id").first()
        assert deleted is None
        db.close()


@patch("app.workers.audio_worker.storage_service.get_local_file_path")
@patch("app.workers.audio_worker.gnani_service.transcribe")
@patch("app.workers.audio_worker.summary_service.generate_summary")
def test_worker_pipeline_success(mock_summary, mock_transcribe, mock_get_path, tmp_path):
    """Verify end-to-end worker completes transcription and summary generation."""
    test_file = tmp_path / "sample.wav"
    test_file.write_bytes(b"dummy wav data")
    mock_get_path.return_value = str(test_file)
    mock_transcribe.return_value = {"transcript": "Welcome to the team meeting today."}
    mock_summary.return_value = "### Overview\nMeeting welcome and kickoff."

    db = SessionLocal()
    note = Note(
        id="worker-test-1",
        file_name="sample.wav",
        storage_key="audio/worker-test-1/sample.wav",
        file_size=500,
        mime_type="audio/wav",
        status=NoteStatus.QUEUED.value,
        progress=10,
        current_stage="Queued",
    )
    db.add(note)
    db.commit()
    db.close()

    # Run worker processing directly
    process_audio_note("worker-test-1")

    db = SessionLocal()
    processed = db.query(Note).filter(Note.id == "worker-test-1").first()
    assert processed.status == NoteStatus.COMPLETED.value
    assert processed.progress == 100
    assert processed.transcript == "Welcome to the team meeting today."
    assert "Overview" in processed.summary
    assert processed.completed_at is not None
    assert processed.error_message is None
    db.close()


@patch("app.workers.audio_worker.storage_service.get_local_file_path")
@patch("app.workers.audio_worker.gnani_service.transcribe")
def test_worker_pipeline_transcription_failure(mock_transcribe, mock_get_path, tmp_path):
    """Verify worker sets friendly FAILED status when Gnani service fails."""
    test_file = tmp_path / "sample.wav"
    test_file.write_bytes(b"dummy wav data")
    mock_get_path.return_value = str(test_file)
    mock_transcribe.side_effect = GnaniTimeoutError("Gnani timed out")

    db = SessionLocal()
    note = Note(
        id="worker-fail-1",
        file_name="sample.wav",
        storage_key="audio/worker-fail-1/sample.wav",
        file_size=500,
        mime_type="audio/wav",
        status=NoteStatus.QUEUED.value,
        progress=10,
        current_stage="Queued",
    )
    db.add(note)
    db.commit()
    db.close()

    process_audio_note("worker-fail-1")

    db = SessionLocal()
    failed_note = db.query(Note).filter(Note.id == "worker-fail-1").first()
    assert failed_note.status == NoteStatus.FAILED.value
    assert "timed out" in failed_note.error_message.lower()
    assert "Failed:" in failed_note.current_stage
    db.close()


def test_get_note_audio_stream(tmp_path):
    """Verify GET /api/notes/{id}/audio streams the audio file safely."""
    test_audio = tmp_path / "stream_sample.wav"
    test_audio.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00")

    db = SessionLocal()
    n = Note(
        id="audio-stream-test",
        file_name="stream_sample.wav",
        storage_key=str(test_audio),
        file_size=28,
        mime_type="audio/wav",
        status=NoteStatus.COMPLETED.value,
        progress=100,
        current_stage="Completed",
    )
    db.add(n)
    db.commit()
    db.close()

    with patch("app.api.notes.storage_service.get_local_file_path", return_value=str(test_audio)):
        response = client.get("/api/notes/audio-stream-test/audio")
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        assert len(response.content) == 24

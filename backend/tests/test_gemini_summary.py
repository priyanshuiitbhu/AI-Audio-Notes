import pytest
from unittest.mock import patch, MagicMock
from app.database import Base, engine, SessionLocal
from app.models.note import Note, NoteStatus
from app.services.summary_service import (
    SummaryService,
    GeminiError,
    GeminiAuthError,
    GeminiRateLimitError,
    GeminiTimeoutError,
)
from app.workers.audio_worker import process_audio_note


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    db = SessionLocal()
    db.query(Note).delete()
    db.commit()
    db.close()


def test_gemini_empty_or_whitespace_transcript():
    """Summary service should handle empty or whitespace transcript gracefully without calling Gemini."""
    service = SummaryService()
    assert "No speech content" in service.generate_summary("")
    assert "No speech content" in service.generate_summary("   \n\t  ")


def test_gemini_fallback_when_no_api_key():
    """When GEMINI_API_KEY is unset, summary service falls back to structured extractive summary."""
    with patch("app.services.summary_service.settings.GEMINI_API_KEY", ""):
        service = SummaryService()
        result = service.generate_summary("This is an important team sync about product release dates and bug fixes.")
        assert "## Overview" in result
        assert "## Key Points" in result


def test_gemini_successful_summary():
    """Summary service calls Gemini with prompt and returns structured markdown."""
    service = SummaryService()
    service.api_key = "dummy-test-key"

    expected_output = """## Overview
The team reviewed Q3 sprint deliverables.

## Key Points
- Core API completed
- Latency reduced by 40%

## Important Details
Release scheduled for Friday at 10 AM UTC.

## Action Items
- Priyanshu to deploy staging build"""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = expected_output
    mock_client.models.generate_content.return_value = mock_response

    with patch.object(service, "_get_client", return_value=mock_client):
        result = service.generate_summary("Today we finished the core API and reduced latency by 40%. Release is Friday.")
        assert result == expected_output
        assert mock_client.models.generate_content.called
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        assert service.model_name in call_kwargs.get("model", "")


def test_gemini_empty_response_raises_error():
    """Summary service raises GeminiError when Gemini returns an empty response."""
    service = SummaryService()
    service.api_key = "dummy-test-key"

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = ""
    mock_client.models.generate_content.return_value = mock_response

    with patch.object(service, "_get_client", return_value=mock_client):
        with pytest.raises(GeminiError) as exc_info:
            service.generate_summary("Some transcript text.")
        assert "empty" in str(exc_info.value).lower()


def test_gemini_auth_error_no_retry():
    """401/403 errors should raise GeminiAuthError immediately without retrying 3 times."""
    service = SummaryService()
    service.api_key = "invalid-key"

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("403 Forbidden: API key expired")

    with patch.object(service, "_get_client", return_value=mock_client):
        with pytest.raises(GeminiAuthError):
            service.generate_summary("Some transcript text.")
        # Must only call once because auth errors are not retryable
        assert mock_client.models.generate_content.call_count == 1


def test_gemini_rate_limit_retry():
    """429 Resource Exhausted should trigger retry and eventually raise GeminiRateLimitError."""
    service = SummaryService()
    service.api_key = "dummy-key"

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("429 Resource Exhausted: Rate limit exceeded")

    with patch.object(service, "_get_client", return_value=mock_client):
        with patch("time.sleep"):  # fast-forward retries
            with pytest.raises(GeminiRateLimitError):
                service.generate_summary("Some transcript text.")
            assert mock_client.models.generate_content.call_count == 3


def test_gemini_timeout_error():
    """Timeout exceptions should be mapped to GeminiTimeoutError."""
    service = SummaryService()
    service.api_key = "dummy-key"

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TimeoutError("Connection timed out")

    with patch.object(service, "_get_client", return_value=mock_client):
        with patch("time.sleep"):
            with pytest.raises(GeminiTimeoutError):
                service.generate_summary("Some transcript text.")
            assert mock_client.models.generate_content.call_count == 3


def test_hierarchical_summarization_large_transcript():
    """Transcripts over 15,000 words trigger hierarchical chunking before final synthesis."""
    service = SummaryService()
    service.api_key = "dummy-key"

    # Create 16,000 words
    large_transcript = "word " * 16000

    mock_client = MagicMock()
    mock_chunk_resp = MagicMock()
    mock_chunk_resp.text = "Intermediate chunk summary."
    mock_final_resp = MagicMock()
    mock_final_resp.text = "## Overview\nFinal combined summary."
    mock_client.models.generate_content.side_effect = [mock_chunk_resp, mock_chunk_resp, mock_final_resp]

    with patch.object(service, "_get_client", return_value=mock_client):
        result = service.generate_summary(large_transcript)
        assert "## Overview" in result
        # 2 chunks + 1 final combination = 3 calls
        assert mock_client.models.generate_content.call_count == 3


@patch("app.workers.audio_worker.storage_service.get_local_file_path")
@patch("app.workers.audio_worker.gnani_service.transcribe")
@patch("app.workers.audio_worker.summary_service.generate_summary")
def test_worker_preserves_transcript_on_gemini_failure(mock_summary, mock_transcribe, mock_get_path, tmp_path):
    """
    CRITICAL REQUIREMENT:
    When Gnani ASR transcribes successfully but Gemini fails, the transcript MUST be preserved
    in the database and NOT deleted or wiped.
    """
    test_file = tmp_path / "meeting.wav"
    test_file.write_bytes(b"dummy wav data")
    mock_get_path.return_value = str(test_file)
    captured_transcript = "This is a pristine transcript that took real compute and Gnani credits."
    mock_transcribe.return_value = {"transcript": captured_transcript}
    mock_summary.side_effect = GeminiRateLimitError("Gemini quota exceeded. Please retry in a few moments.")

    db = SessionLocal()
    note = Note(
        id="note-gemini-fail",
        file_name="meeting.wav",
        storage_key="audio/note-gemini-fail/meeting.wav",
        file_size=1024,
        mime_type="audio/wav",
        status=NoteStatus.QUEUED.value,
        progress=10,
        current_stage="Queued",
    )
    db.add(note)
    db.commit()
    db.close()

    process_audio_note("note-gemini-fail")

    db = SessionLocal()
    failed_note = db.query(Note).filter(Note.id == "note-gemini-fail").first()
    assert failed_note.status == NoteStatus.FAILED.value
    assert "rate limit" in failed_note.error_message.lower()
    # TRANSCRIPT MUST BE INTACT
    assert failed_note.transcript == captured_transcript
    assert failed_note.summary is None
    db.close()


@patch("app.workers.audio_worker.storage_service.get_local_file_path")
@patch("app.workers.audio_worker.gnani_service.transcribe")
@patch("app.workers.audio_worker.summary_service.generate_summary")
def test_worker_skips_gnani_on_retry_when_transcript_exists(mock_summary, mock_transcribe, mock_get_path, tmp_path):
    """
    When retrying a note where transcript was already generated, skip Gnani STT and only run Gemini.
    """
    test_file = tmp_path / "meeting.wav"
    test_file.write_bytes(b"dummy wav data")
    mock_get_path.return_value = str(test_file)

    existing_transcript = "Existing validated transcription text."
    mock_summary.return_value = "## Overview\nSuccessfully generated on retry."

    db = SessionLocal()
    note = Note(
        id="note-retry-skip-gnani",
        file_name="meeting.wav",
        storage_key="audio/note-retry-skip-gnani/meeting.wav",
        file_size=1024,
        mime_type="audio/wav",
        status=NoteStatus.QUEUED.value,
        progress=10,
        current_stage="Queued",
        transcript=existing_transcript,  # Already exists!
        error_message=None,
    )
    db.add(note)
    db.commit()
    db.close()

    process_audio_note("note-retry-skip-gnani")

    # Gnani must NOT have been called!
    assert not mock_transcribe.called
    # Gemini MUST have been called with existing transcript
    mock_summary.assert_called_once_with(existing_transcript)

    db = SessionLocal()
    completed_note = db.query(Note).filter(Note.id == "note-retry-skip-gnani").first()
    assert completed_note.status == NoteStatus.COMPLETED.value
    assert completed_note.transcript == existing_transcript
    assert "Successfully generated" in completed_note.summary
    assert completed_note.error_message is None
    db.close()

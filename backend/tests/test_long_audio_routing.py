import os
import wave
import pytest
from unittest.mock import patch, MagicMock
from app.services.gnani_service import GnaniService, GnaniInvalidAudioError
from app.utils.audio_utils import (
    get_audio_duration_seconds,
    split_wav_file,
    split_audio_file,
    cleanup_temp_files,
    convert_to_wav,
)


def create_dummy_wav(path: str, duration_sec: float, sample_rate: int = 8000):
    """Generates a valid PCM WAV file with specified duration in seconds."""
    num_frames = int(duration_sec * sample_rate)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # Write silence frames (2 bytes per frame for 16-bit)
        wf.writeframes(b"\x00\x00" * num_frames)


def test_audio_duration_detection(tmp_path):
    """Verify accurate duration detection for various durations."""
    for dur in [10.0, 28.0, 30.0, 31.0, 60.0, 120.0, 130.4]:
        file_path = str(tmp_path / f"test_{int(dur)}s.wav")
        create_dummy_wav(file_path, dur)
        detected = get_audio_duration_seconds(file_path)
        assert detected is not None
        assert abs(detected - dur) < 0.05


def test_short_audio_routing_under_28s(tmp_path):
    """Verify audio <= 28 seconds routes directly to transcribe_file_single."""
    file_path = str(tmp_path / "short_10s.wav")
    create_dummy_wav(file_path, 10.0)

    service = GnaniService(api_key="mock_key")
    with patch.object(service, "transcribe_file_single") as mock_single:
        mock_single.return_value = {
            "transcript": "this is short audio",
            "request_id": "req-10s",
            "model": "gnani-prisma-v2.5",
        }

        result = service.transcribe(file_path, language_code="en-IN")
        assert result["transcript"] == "this is short audio"
        assert mock_single.call_count == 1
        mock_single.assert_called_once_with(file_path, language_code="en-IN")


def test_long_audio_routing_over_28s_chunks_properly(tmp_path):
    """
    Verify audio > 28 seconds (e.g. 130s = 2m 10s) splits into ~24s chunks,
    calls transcribe_file_single for each chunk, and combines transcripts in order.
    """
    file_path = str(tmp_path / "long_130s.wav")
    create_dummy_wav(file_path, 130.0)

    service = GnaniService(api_key="mock_key")

    call_index = 0
    def mock_transcribe_chunk(chunk_path, language_code="en-IN"):
        nonlocal call_index
        call_index += 1
        return {
            "transcript": f"segment_{call_index}",
            "request_id": f"chunk_req_{call_index}",
        }

    progress_reports = []
    def record_progress(pct, stage):
        progress_reports.append((pct, stage))

    with patch.object(service, "transcribe_file_single", side_effect=mock_transcribe_chunk):
        result = service.transcribe(file_path, language_code="en-IN", progress_callback=record_progress)

        # 130s / 24s per chunk = 6 chunks (5 * 24s + 1 * 10s)
        assert result["chunk_count"] == 6
        assert call_index == 6
        assert result["transcript"] == "segment_1 segment_2 segment_3 segment_4 segment_5 segment_6"

        # Verify progress was reported incrementally
        assert len(progress_reports) == 6
        assert "segment 1 of 6" in progress_reports[0][1]
        assert "segment 6 of 6" in progress_reports[-1][1]
        assert progress_reports[-1][0] == 70


@pytest.mark.parametrize(
    ("duration", "expected_chunks"),
    [(30.0, 2), (31.0, 2), (60.0, 3), (120.0, 5), (130.0, 6)],
)
def test_required_duration_boundaries_never_send_long_audio_to_short_endpoint(
    tmp_path, duration, expected_chunks
):
    """Every requested boundary uses only <=24s calls to Gnani's short endpoint."""
    file_path = str(tmp_path / f"boundary_{int(duration)}s.wav")
    create_dummy_wav(file_path, duration)
    service = GnaniService(api_key="mock_key")
    called_durations = []

    def mock_transcribe_chunk(chunk_path, language_code="en-IN"):
        chunk_duration = get_audio_duration_seconds(chunk_path)
        called_durations.append(chunk_duration)
        return {"transcript": f"segment_{len(called_durations)}"}

    with patch.object(service, "transcribe_file_single", side_effect=mock_transcribe_chunk):
        result = service.transcribe(file_path, language_code="en-IN")

    assert result["chunk_count"] == expected_chunks
    assert len(called_durations) == expected_chunks
    assert all(value is not None and value <= 24.01 for value in called_durations)
    assert get_audio_duration_seconds(file_path) == pytest.approx(duration, abs=0.05)


def test_failed_split_uses_batch_and_preserves_source_file(tmp_path):
    """A long file is never sent whole to the 30-second endpoint if splitting fails."""
    file_path = str(tmp_path / "unsplittable_130s.wav")
    create_dummy_wav(file_path, 130.0)
    service = GnaniService(api_key="mock_key")

    with patch("app.services.gnani_service.split_audio_file", return_value=([file_path], [])):
        with patch.object(
            service,
            "transcribe_batch_long_audio",
            return_value={"transcript": "batch transcript", "request_id": "batch-1"},
        ) as mock_batch:
            with patch.object(service, "transcribe_file_single") as mock_single:
                result = service.transcribe(file_path, language_code="en-IN")

    assert result["transcript"] == "batch transcript"
    mock_batch.assert_called_once()
    mock_single.assert_not_called()
    assert os.path.exists(file_path)


def test_duration_limit_fallback_reroutes_to_chunks(tmp_path):
    """
    If normal STT unexpectedly raises duration limit error (e.g. strict 30s),
    it should catch the error and re-route to chunking automatically.
    """
    file_path = str(tmp_path / "edge_30s.wav")
    create_dummy_wav(file_path, 28.0)  # At boundary

    service = GnaniService(api_key="mock_key")

    first_call = True
    def mock_flaky_single(path, language_code="en-IN"):
        nonlocal first_call
        if first_call:
            first_call = False
            raise GnaniInvalidAudioError("Gnani rejected audio format: Audio duration exceeds maximum allowed duration of 30 seconds")
        return {"transcript": "recovered chunk"}

    with patch.object(service, "transcribe_file_single", side_effect=mock_flaky_single):
        result = service.transcribe(file_path, language_code="en-IN")
        assert "recovered chunk" in result["transcript"]

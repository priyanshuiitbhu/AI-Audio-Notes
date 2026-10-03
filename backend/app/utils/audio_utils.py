import os
import re
import wave
import tempfile
import subprocess
import logging
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".aac", ".m4a"}
SUPPORTED_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/flac",
    "audio/aac",
    "audio/x-m4a",
    "audio/m4a",
    "audio/mp4",
    "video/mp4",  # Often used for m4a files
    "application/octet-stream",
}


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes user uploaded filename to prevent directory traversal and harmful characters.
    """
    if not filename:
        return "unnamed_audio.wav"

    # Strip path components
    base_name = os.path.basename(filename)

    # Separate stem and ext
    name_part, ext = os.path.splitext(base_name)
    ext = ext.lower().strip()

    # Clean the name part
    clean_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name_part)
    clean_name = re.sub(r"_+", "_", clean_name).strip("_")

    if not clean_name:
        clean_name = "audio"

    # Limit length
    clean_name = clean_name[:64]

    return f"{clean_name}{ext}"


def validate_audio_file(filename: str, file_size: int, content_type: Optional[str] = None) -> Tuple[bool, str]:
    """
    Validates audio file size and format.
    Returns (is_valid, error_message).
    """
    if file_size <= 0:
        return False, "The uploaded file is empty (0 bytes). Please upload a valid audio recording."

    max_bytes = 100 * 1024 * 1024  # 100 MB limit
    if file_size > max_bytes:
        return False, f"File size ({file_size / (1024*1024):.1f} MB) exceeds the maximum allowed limit of 100 MB."

    _, ext = os.path.splitext(filename.lower())
    if ext not in SUPPORTED_EXTENSIONS:
        return (
            False,
            f"Unsupported audio format '{ext}'. Please upload an MP3, WAV, M4A, AAC, OGG, or FLAC file."
        )

    if content_type and content_type.lower() not in SUPPORTED_MIME_TYPES:
        logger.warning(f"Unrecognized MIME type '{content_type}', but extension '{ext}' is allowed.")

    return True, ""


def convert_to_wav(input_path: str) -> Tuple[str, bool]:
    """
    Converts any supported audio format (MP3, M4A, AAC, FLAC, OGG, etc.) to 16-bit PCM WAV.
    Returns (wav_file_path, is_temporary_file).
    If the file is already a valid WAV, returns (input_path, False).
    """
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".wav":
        try:
            with wave.open(input_path, "rb") as wf:
                if wf.getnframes() > 0:
                    return input_path, False
        except Exception:
            pass

    fd, tmp_wav = tempfile.mkstemp(suffix=".wav", prefix="conv_")
    os.close(fd)

    # 1. Try macOS built-in afconvert (fast, zero external dependency)
    if os.path.exists("/usr/bin/afconvert"):
        cmd = ["/usr/bin/afconvert", input_path, "-f", "WAVE", "-d", "LEI16", tmp_wav]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(tmp_wav) and os.path.getsize(tmp_wav) > 0:
            return tmp_wav, True

    # 2. Try ffmpeg (standard in Linux/Docker containers)
    try:
        cmd = ["ffmpeg", "-y", "-i", input_path, "-acodec", "pcm_s16le", tmp_wav]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(tmp_wav) and os.path.getsize(tmp_wav) > 0:
            return tmp_wav, True
    except FileNotFoundError:
        pass

    # 3. Try pydub fallback if installed and configured
    try:
        import pydub
        seg = pydub.AudioSegment.from_file(input_path)
        seg.export(tmp_wav, format="wav")
        if os.path.exists(tmp_wav) and os.path.getsize(tmp_wav) > 0:
            return tmp_wav, True
    except Exception as pe:
        logger.debug(f"pydub audio conversion failed: {pe}")

    if os.path.exists(tmp_wav):
        try:
            os.remove(tmp_wav)
        except OSError:
            pass

    return input_path, False


def get_audio_duration_seconds(file_path: str) -> Optional[float]:
    """
    Accurately determines audio duration in seconds.
    Works for any supported format by reading WAV directly or converting temporarily.
    """
    # 1. Try direct wave header inspection
    try:
        with wave.open(file_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return float(frames) / float(rate)
    except Exception:
        pass

    # 2. Convert to temporary WAV and read frames/framerate
    wav_path, is_temp = convert_to_wav(file_path)
    if is_temp:
        try:
            with wave.open(wav_path, "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    return float(frames) / float(rate)
        except Exception as e:
            logger.debug(f"Could not read duration from converted WAV: {e}")
        finally:
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

    # 3. Fallback to pydub if available
    try:
        import pydub
        seg = pydub.AudioSegment.from_file(file_path)
        return len(seg) / 1000.0
    except Exception as e:
        logger.debug(f"Could not determine audio duration from pydub: {e}")

    return None


def split_wav_file(file_path: str, chunk_duration_sec: int = 24) -> List[str]:
    """
    Splits a WAV file into smaller WAV chunks using the standard wave library.
    Ensures safe segmenting without external tools.
    """
    chunk_paths = []
    try:
        with wave.open(file_path, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            total_frames = wf.getnframes()
            total_duration = total_frames / framerate

            if total_duration <= (chunk_duration_sec + 2):
                return [file_path]

            frames_per_chunk = chunk_duration_sec * framerate
            temp_dir = tempfile.mkdtemp(prefix="audio_chunks_")

            chunk_idx = 0
            while True:
                frames = wf.readframes(frames_per_chunk)
                if not frames:
                    break

                chunk_filename = os.path.join(temp_dir, f"chunk_{chunk_idx:03d}.wav")
                with wave.open(chunk_filename, "wb") as out_wf:
                    out_wf.setnchannels(n_channels)
                    out_wf.setsampwidth(sampwidth)
                    out_wf.setframerate(framerate)
                    out_wf.writeframes(frames)

                chunk_paths.append(chunk_filename)
                chunk_idx += 1

        logger.info(f"Split {file_path} into {len(chunk_paths)} chunks")
        return chunk_paths
    except Exception as e:
        logger.warning(f"Wave splitting failed: {e}. Returning original file.")
        return [file_path]


def split_audio_file(file_path: str, chunk_duration_sec: int = 24) -> Tuple[List[str], List[str]]:
    """
    Splits any audio file (WAV, MP3, M4A, etc.) into smaller WAV chunks.
    Returns (chunk_paths, temp_files_to_cleanup).
    """
    temp_files = []
    wav_path, is_temp = convert_to_wav(file_path)
    if is_temp:
        temp_files.append(wav_path)

    chunks = split_wav_file(wav_path, chunk_duration_sec=chunk_duration_sec)
    return chunks, temp_files


def cleanup_temp_files(files: List[str]):
    """Safely cleans up temporary files and directories."""
    cleaned_dirs = set()
    for f in files:
        try:
            if os.path.isfile(f):
                parent = os.path.dirname(f)
                os.remove(f)
                if "audio_chunks_" in parent:
                    cleaned_dirs.add(parent)
        except Exception as e:
            logger.debug(f"Failed to cleanup temp file {f}: {e}")

    for d in cleaned_dirs:
        try:
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
        except Exception:
            pass

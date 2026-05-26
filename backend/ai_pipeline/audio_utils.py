"""
ai_pipeline/audio_utils.py — Audio preprocessing helpers.

Handles:
- Video → audio extraction (ffmpeg)
- Audio normalization and resampling to 16kHz mono (Whisper's native format)
- File chunking for very long recordings (>30 min)
- Silence detection and trimming
- Duration and metadata extraction via ffprobe
"""

import os
import logging
import subprocess
import tempfile
import json
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Whisper's preferred sample rate
WHISPER_SAMPLE_RATE = 16_000

# Chunk length in seconds for long recordings
CHUNK_SECONDS = 600   # 10-minute chunks


# ── ffprobe helpers ────────────────────────────────────────────────────────────

def get_media_info(file_path: str) -> dict:
    """
    Extract duration, codec, channels, and sample rate using ffprobe.
    Returns a dict; falls back to empty dict on failure.
    """
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            fmt  = data.get("format", {})
            streams = data.get("streams", [])
            audio_stream = next(
                (s for s in streams if s.get("codec_type") == "audio"), {}
            )
            return {
                "duration":    float(fmt.get("duration", 0)),
                "size":        int(fmt.get("size", 0)),
                "format_name": fmt.get("format_name", ""),
                "codec":       audio_stream.get("codec_name", ""),
                "channels":    audio_stream.get("channels", 1),
                "sample_rate": int(audio_stream.get("sample_rate", 0)),
                "bit_rate":    int(fmt.get("bit_rate", 0)),
            }
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        logger.warning(f"ffprobe failed for {file_path}: {e}")
    return {}


def get_duration(file_path: str) -> int:
    """Return file duration in seconds (integer). Returns 0 on failure."""
    info = get_media_info(file_path)
    return int(info.get("duration", 0))


# ── Audio extraction ───────────────────────────────────────────────────────────

def is_video_file(file_path: str) -> bool:
    """Detect video files by extension."""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in {".mp4", ".avi", ".mkv", ".webm", ".mov", ".m4v", ".flv"}


def extract_audio(
    input_path: str,
    output_path: Optional[str] = None,
    sample_rate: int = WHISPER_SAMPLE_RATE,
    channels: int = 1,
) -> str:
    """
    Extract and normalize audio from any audio/video file.
    Output is a 16kHz mono WAV file suitable for Whisper.

    Args:
        input_path:  Source file (audio or video)
        output_path: Destination WAV path; auto-generates temp file if None
        sample_rate: Target sample rate (default 16000 Hz)
        channels:    Number of output channels (1 = mono)

    Returns:
        Path to the extracted WAV file
    """
    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        output_path = tmp.name

    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-vn",                           # strip video track
        "-acodec", "pcm_s16le",          # 16-bit PCM (Whisper requirement)
        "-ar", str(sample_rate),         # resample
        "-ac", str(channels),            # mono
        "-af", "loudnorm",               # normalize loudness (EBU R128)
        "-y",                            # overwrite
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            # Retry without loudnorm (some codecs reject it)
            logger.warning(f"Audio extraction with loudnorm failed, retrying plain: {result.stderr[:200]}")
            cmd_plain = [c for c in cmd if c != "loudnorm" and c != "-af"]
            result2   = subprocess.run(cmd_plain, capture_output=True, text=True, timeout=600)
            if result2.returncode != 0:
                raise RuntimeError(f"ffmpeg extraction failed: {result2.stderr[:300]}")
        logger.info(f"Audio extracted: {output_path} ({os.path.getsize(output_path)//1024} KB)")
        return output_path
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg audio extraction timed out (>10 min)")


# ── Chunking for long recordings ───────────────────────────────────────────────

def split_audio(
    audio_path: str,
    chunk_seconds: int = CHUNK_SECONDS,
) -> List[Tuple[str, float]]:
    """
    Split a long audio file into overlapping chunks for parallel/sequential
    Whisper transcription. Returns list of (chunk_path, start_offset_seconds).

    Adds 2 seconds of overlap between chunks to avoid cutting mid-sentence.
    """
    info     = get_media_info(audio_path)
    duration = info.get("duration", 0)

    if duration <= chunk_seconds:
        # Short file — no splitting needed
        return [(audio_path, 0.0)]

    logger.info(f"Splitting {duration:.0f}s audio into {chunk_seconds}s chunks")

    chunks     = []
    start      = 0.0
    overlap    = 2.0   # seconds of overlap
    chunk_idx  = 0

    while start < duration:
        end       = min(start + chunk_seconds, duration)
        chunk_len = end - start

        tmp = tempfile.NamedTemporaryFile(
            suffix=f"_chunk{chunk_idx:03d}.wav", delete=False
        )
        tmp.close()
        chunk_path = tmp.name

        cmd = [
            "ffmpeg",
            "-i", audio_path,
            "-ss", str(start),
            "-t",  str(chunk_len + overlap),
            "-acodec", "copy",
            "-y",
            chunk_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            chunks.append((chunk_path, start))
            logger.debug(f"Chunk {chunk_idx}: {start:.1f}s → {end:.1f}s → {chunk_path}")
        else:
            logger.warning(f"Chunk {chunk_idx} extraction failed: {result.stderr[:100]}")

        start      = end
        chunk_idx += 1

    return chunks


def cleanup_temp_files(paths: List[str]) -> None:
    """Remove temporary chunk files."""
    for p in paths:
        try:
            if os.path.exists(p):
                os.unlink(p)
                logger.debug(f"Cleaned up: {p}")
        except OSError as e:
            logger.warning(f"Could not remove temp file {p}: {e}")


# ── Silence / quality detection ────────────────────────────────────────────────

def detect_silence_ratio(audio_path: str, noise_tolerance: float = -40.0) -> float:
    """
    Estimate the fraction of the file that is silent using ffmpeg silencedetect.
    Returns a value between 0.0 (all speech) and 1.0 (all silent).
    Useful for flagging recordings that are unlikely to produce good transcripts.
    """
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", f"silencedetect=noise={noise_tolerance}dB:d=0.5",
        "-f", "null", "-",
    ]
    try:
        result  = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output  = result.stderr

        import re
        # Extract silence durations
        durations = re.findall(r"silence_duration: ([\d.]+)", output)
        total_sil = sum(float(d) for d in durations)

        info     = get_media_info(audio_path)
        duration = info.get("duration", 1) or 1
        ratio    = min(total_sil / duration, 1.0)
        logger.info(f"Silence ratio: {ratio:.1%} of {duration:.0f}s")
        return ratio
    except Exception as e:
        logger.warning(f"Silence detection failed: {e}")
        return 0.0


def validate_audio_file(file_path: str) -> Tuple[bool, str]:
    """
    Validate that the file is a readable audio/video file.
    Returns (is_valid, reason_if_invalid).
    """
    if not os.path.exists(file_path):
        return False, "File not found"

    if os.path.getsize(file_path) < 1024:
        return False, "File is too small (< 1 KB)"

    info = get_media_info(file_path)
    if not info:
        return False, "Could not read file metadata (not a valid audio/video file)"

    duration = info.get("duration", 0)
    if duration < 1:
        return False, "File duration is less than 1 second"

    if duration > 7200:
        return False, "File is longer than 2 hours — please trim and re-upload"

    return True, ""

"""
services/stt_service.py — Speech-to-Text via OpenAI Whisper.

Features:
- Lazy model loading with shared cache (no reload between jobs)
- Video-to-audio extraction before transcription
- Automatic chunking for recordings > 10 minutes
- Chunk-level retry with exponential back-off
- Segment stitching with corrected timestamps
- Language detection + confidence score
- Speaker diarization via pyannote-audio (optional)
- Fallback gracefully when heavy deps are missing
"""

import os
import gc
import time
import logging
import tempfile
from typing import List, Dict, Optional, Tuple

from ai_pipeline import get_cached_model
from ai_pipeline.audio_utils import (
    extract_audio, is_video_file, split_audio,
    cleanup_temp_files, validate_audio_file, detect_silence_ratio, get_duration,
)

logger = logging.getLogger(__name__)

MAX_RETRIES   = 3
RETRY_BACKOFF = 2


# ── Model loading ──────────────────────────────────────────────────────────────

def _load_whisper(model_name: str):
    import whisper
    try:
        return whisper.load_model(model_name)
    except RuntimeError as e:
        if "memory" in str(e).lower():
            logger.warning(f"OOM loading '{model_name}', falling back to 'base'")
            return whisper.load_model("base")
        raise


def _get_model(model_name: str = "base"):
    return get_cached_model(f"whisper:{model_name}", lambda: _load_whisper(model_name))


# ── Core transcription ─────────────────────────────────────────────────────────

def _transcribe_chunk(model, audio_path: str, language: Optional[str], prompt: str = "") -> dict:
    opts = {
        "task":                          "transcribe",
        "verbose":                       False,
        "fp16":                          False,
        "condition_on_previous_text":    True,
        "no_speech_threshold":           0.6,
        "logprob_threshold":             -1.0,
        "compression_ratio_threshold":   2.4,
    }
    if language:
        opts["language"] = language
    if prompt:
        opts["initial_prompt"] = prompt[-200:]

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return model.transcribe(audio_path, **opts)
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise
            wait = RETRY_BACKOFF ** attempt
            logger.warning(f"Whisper attempt {attempt} failed ({e}) — retry in {wait}s")
            time.sleep(wait)


def _stitch_segments(chunk_results: List[Tuple[dict, float]]) -> Tuple[str, List[dict]]:
    """Merge per-chunk results, correcting timestamps and de-duping overlaps."""
    all_segs, texts = [], []

    for result, start_offset in chunk_results:
        txt = (result.get("text") or "").strip()
        if txt:
            texts.append(txt)
        for seg in result.get("segments", []):
            all_segs.append({
                "start":          round(seg["start"] + start_offset, 2),
                "end":            round(seg["end"]   + start_offset, 2),
                "text":           seg["text"].strip(),
                "avg_logprob":    round(seg.get("avg_logprob", 0), 4),
                "no_speech_prob": round(seg.get("no_speech_prob", 0), 4),
            })

    # De-dup overlapping boundary segments
    cleaned = []
    for seg in sorted(all_segs, key=lambda s: s["start"]):
        if not seg["text"]:
            continue
        if cleaned and seg["start"] < cleaned[-1]["end"] - 0.5:
            if seg["avg_logprob"] > cleaned[-1]["avg_logprob"]:
                cleaned[-1] = seg
        else:
            cleaned.append(seg)

    full_text = " ".join(texts) if texts else " ".join(s["text"] for s in cleaned)
    return full_text.strip(), cleaned


def _detect_language(model, audio_path: str) -> Tuple[str, float]:
    try:
        import whisper
        audio = whisper.load_audio(audio_path)
        audio = whisper.pad_or_trim(audio)
        mel   = whisper.log_mel_spectrogram(audio).to(model.device)
        _, probs = model.detect_language(mel)
        lang  = max(probs, key=probs.get)
        prob  = round(float(probs[lang]), 4)
        logger.info(f"Language detected: {lang} ({prob:.1%})")
        return lang, prob
    except Exception as e:
        logger.warning(f"Language detection failed ({e}) — defaulting 'en'")
        return "en", 0.0


# ── Speaker diarization ────────────────────────────────────────────────────────

def _diarize(audio_path: str, segments: List[dict]) -> List[dict]:
    """Assign speaker labels; falls back to 'Speaker 1' gracefully."""
    try:
        from pyannote.audio import Pipeline
        hf_token = os.getenv("HUGGINGFACE_TOKEN", "")
        if not hf_token:
            raise ImportError("HUGGINGFACE_TOKEN not set")

        pipeline = get_cached_model(
            "pyannote:speaker-diarization",
            lambda: Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token,
            ),
        )
        diarization   = pipeline(audio_path)
        speaker_turns = [
            (t.start, t.end, lbl)
            for t, _, lbl in diarization.itertracks(yield_label=True)
        ]

        def best_speaker(s_start, s_end):
            best, best_ov = "Speaker 1", 0.0
            for t_s, t_e, lbl in speaker_turns:
                ov = max(0, min(s_end, t_e) - max(s_start, t_s))
                if ov > best_ov:
                    best_ov = ov
                    num  = int(lbl.replace("SPEAKER_", "")) + 1
                    best = f"Speaker {num}"
            return best

        return [{**s, "speaker": best_speaker(s["start"], s["end"])} for s in segments]

    except Exception as e:
        logger.info(f"Diarization skipped ({e}) — using 'Speaker 1'")
        return [{**s, "speaker": "Speaker 1"} for s in segments]


# ── Post-processing ────────────────────────────────────────────────────────────

def _filter_low_confidence(segs: List[dict], threshold: float = -2.0) -> List[dict]:
    filtered = [s for s in segs if s.get("avg_logprob", 0) >= threshold]
    dropped  = len(segs) - len(filtered)
    if dropped:
        logger.info(f"Filtered {dropped} low-confidence segments")
    return filtered


def _merge_speaker_runs(segments: List[dict]) -> List[dict]:
    """Merge consecutive same-speaker segments for readability."""
    if not segments:
        return []
    merged  = []
    current = dict(segments[0])
    for seg in segments[1:]:
        same    = seg["speaker"] == current["speaker"]
        gap_ok  = seg["start"] - current["end"] < 1.5
        win_ok  = seg["end"]   - current["start"] < 30.0
        if same and gap_ok and win_ok:
            current["text"] += " " + seg["text"]
            current["end"]   = seg["end"]
            current["avg_logprob"] = min(
                current.get("avg_logprob", 0), seg.get("avg_logprob", 0)
            )
        else:
            merged.append(current)
            current = dict(seg)
    merged.append(current)
    return merged


# ── Public API ─────────────────────────────────────────────────────────────────

def transcribe_audio(
    file_path:            str,
    model_name:           str  = "base",
    language:             Optional[str] = None,
    enable_diarization:   bool = True,
) -> dict:
    """
    Full speech-to-text pipeline. Returns:
      { full_text, language, language_prob, segments, duration_seconds,
        word_count, silence_ratio }
    """
    tmp_wav    = None
    chunk_tmps = []

    try:
        valid, reason = validate_audio_file(file_path)
        if not valid:
            raise ValueError(f"Invalid audio file: {reason}")

        # Normalize to 16kHz mono WAV
        tmp_wav    = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_wav.close()
        audio_path = extract_audio(file_path, tmp_wav.name)

        silence_ratio = detect_silence_ratio(audio_path)
        if silence_ratio > 0.95:
            logger.warning("Recording is >95% silent — transcript quality will be very low")

        model = _get_model(model_name)

        if not language:
            language, lang_prob = _detect_language(model, audio_path)
        else:
            lang_prob = 1.0

        chunks = split_audio(audio_path)
        logger.info(f"Transcribing {len(chunks)} chunk(s) with Whisper '{model_name}'")

        chunk_results = []
        rolling_ctx   = ""
        for chunk_path, start_offset in chunks:
            if chunk_path != audio_path:
                chunk_tmps.append(chunk_path)
            result = _transcribe_chunk(model, chunk_path, language, rolling_ctx)
            chunk_results.append((result, start_offset))
            rolling_ctx += " " + (result.get("text") or "")

        full_text, segments = _stitch_segments(chunk_results)
        segments            = _filter_low_confidence(segments)

        if enable_diarization:
            segments = _diarize(audio_path, segments)
        else:
            segments = [{**s, "speaker": "Speaker 1"} for s in segments]

        segments = _merge_speaker_runs(segments)
        duration = get_duration(audio_path)

        logger.info(
            f"STT done: {len(full_text.split())} words, "
            f"{len(segments)} blocks, lang={language}, {duration}s"
        )
        return {
            "full_text":        full_text,
            "language":         language,
            "language_prob":    lang_prob,
            "segments":         segments,
            "duration_seconds": duration,
            "word_count":       len(full_text.split()),
            "silence_ratio":    round(silence_ratio, 3),
        }
    finally:
        if tmp_wav and os.path.exists(tmp_wav.name):
            os.unlink(tmp_wav.name)
        cleanup_temp_files(chunk_tmps)
        gc.collect()

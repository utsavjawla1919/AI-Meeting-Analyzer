"""
services/speaker_service.py — Advanced speaker analytics.

Computes per-speaker stats beyond basic word count:
  - Talk-time distribution (for pie chart)
  - Speaking pace (words per minute)
  - Interruption detection
  - Question vs statement ratio
  - Engagement score per speaker
  - Turn-taking patterns
"""

import re
import logging
import math
from collections import defaultdict, Counter
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Patterns for question detection
QUESTION_RE = re.compile(
    r"\b(what|where|when|why|how|who|which|could|would|should|can|is|are|do|does|did)\b.*\?",
    re.IGNORECASE,
)

# Filler word patterns
FILLER_RE = re.compile(
    r"\b(um+|uh+|er+|like|you know|i mean|basically|literally|actually|sort of|kind of)\b",
    re.IGNORECASE,
)


def _speaking_pace(word_count: int, duration_s: float) -> float:
    """Words per minute. Returns 0.0 if duration is zero."""
    if duration_s <= 0:
        return 0.0
    return round(word_count / (duration_s / 60), 1)


def _detect_interruptions(segments: List[Dict]) -> List[Dict]:
    """
    Detect likely interruptions: when one speaker's segment starts
    within 0.3s of another speaker's segment ending.
    Returns list of {interrupter, interrupted, at_seconds}.
    """
    interruptions = []
    for i in range(1, len(segments)):
        prev = segments[i - 1]
        curr = segments[i]
        gap  = curr.get("start", 0) - prev.get("end", 0)

        if (
            gap < 0.3
            and curr.get("speaker") != prev.get("speaker")
            and len(curr.get("text", "").split()) >= 3
        ):
            interruptions.append({
                "interrupter":  curr.get("speaker", "Unknown"),
                "interrupted":  prev.get("speaker", "Unknown"),
                "at_seconds":   round(curr.get("start", 0), 2),
            })

    return interruptions


def _question_ratio(text: str) -> float:
    """Fraction of sentences that are questions."""
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 0.0
    questions = sum(1 for s in sentences if QUESTION_RE.search(s) or s.endswith("?"))
    return round(questions / len(sentences), 3)


def _filler_rate(text: str) -> float:
    """Filler words per 100 words spoken."""
    words   = text.split()
    fillers = len(FILLER_RE.findall(text))
    if not words:
        return 0.0
    return round(fillers / len(words) * 100, 2)


def _engagement_score(
    time_pct:       float,
    question_ratio: float,
    filler_rate:    float,
    turn_count:     int,
    total_turns:    int,
) -> int:
    """
    0-100 engagement score per speaker.
    Higher = more engaged, participatory, articulate.
    """
    # Participation (40 pts): not too quiet, not monopolizing
    ideal_pct = 100 / max(total_turns, 1)
    deviation  = abs(time_pct - ideal_pct) / max(ideal_pct, 1)
    part_pts   = round(max(0, 40 - deviation * 30))

    # Inquisitiveness (20 pts): asking questions shows engagement
    q_pts = round(min(question_ratio * 60, 20))

    # Articulateness (20 pts): fewer fillers = better
    filler_pts = round(max(0, 20 - filler_rate * 2))

    # Turn-taking (20 pts): taking multiple turns shows active participation
    turn_ratio = turn_count / max(total_turns, 1)
    turn_pts   = round(min(turn_ratio * 40, 20))

    return min(100, part_pts + q_pts + filler_pts + turn_pts)


def _build_turn_sequence(segments: List[Dict]) -> List[str]:
    """
    Collapse consecutive same-speaker segments into speaker turns.
    Returns ordered list of speaker names (one per turn).
    """
    turns = []
    for seg in segments:
        spk = seg.get("speaker", "Unknown")
        if not turns or turns[-1] != spk:
            turns.append(spk)
    return turns


def compute_speaker_analytics(segments: List[Dict]) -> Dict[str, Any]:
    """
    Full speaker analytics computation.

    Args:
        segments: [{speaker, start, end, text}, ...]

    Returns:
        {
          speakers: {
            <name>: {
              word_count, talk_time_s, talk_time_pct, words_per_min,
              question_ratio, filler_rate, turn_count, turn_pct,
              engagement_score, sentiment_label (filled by caller)
            }
          },
          turn_sequence:    [str, ...]  (ordered speaker turns),
          interruptions:    [{interrupter, interrupted, at_seconds}],
          total_speakers:   int,
          most_active:      str | None,
          most_questions:   str | None,
        }
    """
    if not segments:
        return {
            "speakers": {}, "turn_sequence": [],
            "interruptions": [], "total_speakers": 0,
            "most_active": None, "most_questions": None,
        }

    # Per-speaker accumulators
    word_counts:   Dict[str, int]   = Counter()
    talk_times:    Dict[str, float] = defaultdict(float)
    turn_counts:   Dict[str, int]   = Counter()
    texts:         Dict[str, str]   = defaultdict(str)
    turns_sequence = _build_turn_sequence(segments)

    for seg in segments:
        spk      = seg.get("speaker", "Unknown")
        text     = seg.get("text", "")
        duration = max(0.0, seg.get("end", 0) - seg.get("start", 0))

        word_counts[spk] += len(text.split())
        talk_times[spk]  += duration
        texts[spk]       += " " + text

    for spk in turns_sequence:
        turn_counts[spk] += 1

    total_time  = sum(talk_times.values()) or 1.0
    total_turns = len(turns_sequence)
    all_speakers = set(word_counts) | set(talk_times)

    interruptions = _detect_interruptions(segments)

    speakers = {}
    for spk in all_speakers:
        wc        = word_counts.get(spk, 0)
        dur       = talk_times.get(spk, 0.0)
        turns     = turn_counts.get(spk, 0)
        time_pct  = round(dur / total_time * 100, 1)
        spk_text  = texts.get(spk, "")

        q_ratio  = _question_ratio(spk_text)
        fill_rt  = _filler_rate(spk_text)
        pace     = _speaking_pace(wc, dur)
        eng      = _engagement_score(time_pct, q_ratio, fill_rt, turns, total_turns)

        speakers[spk] = {
            "word_count":      wc,
            "talk_time_s":     round(dur, 1),
            "talk_time_pct":   time_pct,
            "words_per_min":   pace,
            "turn_count":      turns,
            "turn_pct":        round(turns / total_turns * 100, 1) if total_turns else 0.0,
            "question_ratio":  q_ratio,
            "filler_rate":     fill_rt,
            "engagement_score": eng,
            "sentiment_label": None,  # filled by caller after sentiment stage
        }

    most_active    = max(speakers, key=lambda s: speakers[s]["talk_time_s"]) if speakers else None
    most_questions = max(speakers, key=lambda s: speakers[s]["question_ratio"]) if speakers else None

    logger.info(
        f"Speaker analytics: {len(speakers)} speakers, "
        f"{len(interruptions)} interruptions, {total_turns} turns"
    )

    return {
        "speakers":       speakers,
        "turn_sequence":  turns_sequence,
        "interruptions":  interruptions,
        "total_speakers": len(speakers),
        "most_active":    most_active,
        "most_questions": most_questions,
    }

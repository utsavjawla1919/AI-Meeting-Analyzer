"""
services/sentiment_service.py — Multi-level sentiment analysis.

Levels:
  1. Per-segment  (each Whisper transcript segment scored individually)
  2. Per-speaker  (aggregated from that speaker's segments)
  3. Overall      (weighted average across all segments)
  4. Timeline     (sliding window for Chart.js timeline chart)

Models (in priority order):
  1. DistilBERT SST-2 (HuggingFace transformers) — best accuracy
  2. VADER (NLTK)                                 — fast CPU fallback
  3. Simple lexicon                               — last resort
"""

import re
import logging
import math
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple

from ai_pipeline import get_cached_model

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# MODEL LOADING
# ══════════════════════════════════════════════════════════════════════════════

def _get_transformer_pipeline(model_name: str = "distilbert-base-uncased-finetuned-sst-2-english"):
    def _load():
        from transformers import pipeline
        logger.info(f"Loading sentiment model: {model_name}")
        return pipeline(
            "sentiment-analysis",
            model=model_name,
            device=-1,          # CPU; 0 = GPU
            truncation=True,
            max_length=512,
            batch_size=16,      # batch processing for speed
        )
    return get_cached_model(f"sentiment:{model_name}", _load)


def _get_vader():
    def _load():
        import nltk
        try:
            nltk.data.find("sentiment/vader_lexicon.zip")
        except LookupError:
            nltk.download("vader_lexicon", quiet=True)
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        return SentimentIntensityAnalyzer()
    return get_cached_model("vader", _load)


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE-TEXT SCORING
# ══════════════════════════════════════════════════════════════════════════════

def _score_with_transformer(pipe, text: str) -> Dict:
    """
    Score one text with DistilBERT SST-2.
    SST-2 is binary (POSITIVE/NEGATIVE); we derive a neutral zone
    from the confidence margin.
    """
    result    = pipe(text[:512])[0]
    raw_label = result["label"].lower()   # "positive" | "negative"
    raw_score = float(result["score"])    # confidence in the predicted label

    # Neutral zone: if confidence < 0.65, call it neutral
    NEUTRAL_THRESHOLD = 0.65

    if raw_score < NEUTRAL_THRESHOLD:
        label    = "neutral"
        positive = raw_score     if raw_label == "positive" else (1 - raw_score)
        negative = raw_score     if raw_label == "negative" else (1 - raw_score)
        neutral  = 1.0 - max(positive, negative)
    elif raw_label == "positive":
        label    = "positive"
        positive = raw_score
        negative = 1 - raw_score
        neutral  = 0.0
    else:
        label    = "negative"
        negative = raw_score
        positive = 1 - raw_score
        neutral  = 0.0

    return {
        "label":    label,
        "score":    round(raw_score, 4),
        "positive": round(max(positive, 0), 4),
        "negative": round(max(negative, 0), 4),
        "neutral":  round(max(neutral,  0), 4),
    }


def _score_with_vader(sia, text: str) -> Dict:
    """Score one text with NLTK VADER (rule-based, no model download)."""
    scores   = sia.polarity_scores(text)
    compound = scores["compound"]

    if compound >= 0.05:
        label = "positive"
        score = (compound + 1) / 2
    elif compound <= -0.05:
        label = "negative"
        score = (1 - compound) / 2
    else:
        label = "neutral"
        score = 0.5 + abs(compound)

    return {
        "label":    label,
        "score":    round(score, 4),
        "positive": round(scores["pos"], 4),
        "negative": round(scores["neg"], 4),
        "neutral":  round(scores["neu"], 4),
    }


def _score_text(text: str) -> Dict:
    """
    Score a single text string, cascading through available models.
    Returns {label, score, positive, negative, neutral}.
    """
    text = text.strip()
    if not text or len(text.split()) < 3:
        return {"label": "neutral", "score": 0.5,
                "positive": 0.0, "negative": 0.0, "neutral": 1.0}

    # Try transformer first
    try:
        pipe = _get_transformer_pipeline()
        return _score_with_transformer(pipe, text)
    except Exception as e:
        logger.debug(f"Transformer sentiment failed ({e}) — trying VADER")

    # VADER fallback
    try:
        sia = _get_vader()
        return _score_with_vader(sia, text)
    except Exception as e:
        logger.warning(f"VADER fallback failed ({e}) — returning neutral")

    return {"label": "neutral", "score": 0.5,
            "positive": 0.1, "negative": 0.1, "neutral": 0.8}


def _batch_score_texts(texts: List[str]) -> List[Dict]:
    """
    Batch score a list of texts using the transformer pipeline.
    Falls back to per-item VADER on failure.
    """
    if not texts:
        return []

    # Try transformer batch
    try:
        pipe    = _get_transformer_pipeline()
        results = pipe([t[:512] for t in texts])
        scored  = []
        for r in results:
            raw_label = r["label"].lower()
            raw_score = float(r["score"])
            NEUTRAL_T = 0.65
            if raw_score < NEUTRAL_T:
                label    = "neutral"
                positive = raw_score if raw_label == "positive" else (1 - raw_score)
                negative = raw_score if raw_label == "negative" else (1 - raw_score)
                neutral  = 1.0 - max(positive, negative)
            elif raw_label == "positive":
                label, positive, negative, neutral = "positive", raw_score, 1 - raw_score, 0.0
            else:
                label, positive, negative, neutral = "negative", 1 - raw_score, raw_score, 0.0
            scored.append({
                "label":    label,
                "score":    round(raw_score, 4),
                "positive": round(max(positive, 0), 4),
                "negative": round(max(negative, 0), 4),
                "neutral":  round(max(neutral,  0), 4),
            })
        return scored
    except Exception as e:
        logger.warning(f"Batch transformer failed ({e}) — per-item VADER")

    return [_score_text(t) for t in texts]


# ══════════════════════════════════════════════════════════════════════════════
# AGGREGATION
# ══════════════════════════════════════════════════════════════════════════════

def _aggregate(scored_list: List[Dict]) -> Dict:
    """Weighted average of a list of segment scores → overall score object."""
    if not scored_list:
        return {"label": "neutral", "score": 0.5,
                "positive": 0.0, "negative": 0.0, "neutral": 1.0}

    n        = len(scored_list)
    avg_pos  = sum(s["positive"] for s in scored_list) / n
    avg_neg  = sum(s["negative"] for s in scored_list) / n
    avg_neu  = sum(s["neutral"]  for s in scored_list) / n
    avg_sc   = sum(s["score"]    for s in scored_list) / n

    if avg_pos >= avg_neg and avg_pos >= avg_neu:
        label = "positive"
    elif avg_neg > avg_pos and avg_neg >= avg_neu:
        label = "negative"
    else:
        label = "neutral"

    return {
        "label":    label,
        "score":    round(avg_sc,  4),
        "positive": round(avg_pos, 4),
        "negative": round(avg_neg, 4),
        "neutral":  round(avg_neu, 4),
    }


# ══════════════════════════════════════════════════════════════════════════════
# TIMELINE CONSTRUCTION
# ══════════════════════════════════════════════════════════════════════════════

def _build_timeline(
    segments:      List[Dict],
    segment_scores: List[Dict],
    window_size:   int = 5,
) -> List[Dict]:
    """
    Build a smoothed sentiment timeline for Chart.js.
    Uses a sliding window average to reduce noise.

    Returns list of:
      { segment_index, start, speaker, label, score,
        positive, negative, neutral, smoothed_positive, smoothed_negative }
    """
    if not segments or not segment_scores:
        return []

    n      = min(len(segments), len(segment_scores))
    raw    = []
    for i in range(n):
        seg   = segments[i]
        score = segment_scores[i]
        raw.append({
            "segment_index": i,
            "start":         round(seg.get("start", 0), 2),
            "speaker":       seg.get("speaker", "Speaker 1"),
            **score,
        })

    # Sliding-window smoothing
    half = window_size // 2
    for i, point in enumerate(raw):
        window  = raw[max(0, i - half): i + half + 1]
        point["smoothed_positive"] = round(
            sum(w["positive"] for w in window) / len(window), 4
        )
        point["smoothed_negative"] = round(
            sum(w["negative"] for w in window) / len(window), 4
        )
        point["smoothed_neutral"] = round(
            sum(w["neutral"] for w in window) / len(window), 4
        )

    return raw


# ══════════════════════════════════════════════════════════════════════════════
# MEETING HEALTH SCORE
# ══════════════════════════════════════════════════════════════════════════════

def _compute_meeting_health(
    overall:      Dict,
    by_speaker:   Dict,
    timeline:     List[Dict],
    action_count: int = 0,
) -> Dict:
    """
    Compute a composite meeting health score (0-100) and a health label.

    Factors:
      - Overall sentiment positivity  (40%)
      - Sentiment stability           (20%)  — low variance = better
      - Speaker balance               (20%)
      - Actionability                 (20%)
    """
    # 1. Sentiment component (40 pts)
    pos_score = float(overall.get("positive", 0))
    neg_score = float(overall.get("negative", 0))
    sentiment_pts = round((pos_score - neg_score * 0.5) * 40, 1)
    sentiment_pts = max(0, min(40, sentiment_pts + 20))

    # 2. Stability (20 pts) — std-dev of smoothed_positive across timeline
    if timeline:
        poss = [t.get("smoothed_positive", t.get("positive", 0)) for t in timeline]
        mean = sum(poss) / len(poss)
        variance = sum((p - mean) ** 2 for p in poss) / len(poss)
        std_dev  = math.sqrt(variance)
        stability_pts = round(max(0, 20 - std_dev * 60), 1)
    else:
        stability_pts = 10.0

    # 3. Speaker balance (20 pts)
    if by_speaker and len(by_speaker) > 1:
        # Gini coefficient on sentiment scores
        scores = sorted(float(v.get("score", 0.5)) for v in by_speaker.values())
        n      = len(scores)
        gini   = sum(abs(scores[i] - scores[j]) for i in range(n) for j in range(n)) / (2 * n * sum(scores) or 1)
        balance_pts = round((1 - gini) * 20, 1)
    else:
        balance_pts = 14.0  # neutral if single speaker

    # 4. Actionability (20 pts)
    action_pts = min(action_count * 3, 20)

    total = round(sentiment_pts + stability_pts + balance_pts + action_pts)
    total = max(0, min(100, total))

    if total >= 75:
        health_label = "Excellent"
    elif total >= 55:
        health_label = "Good"
    elif total >= 35:
        health_label = "Fair"
    else:
        health_label = "Needs Attention"

    return {
        "score":        total,
        "label":        health_label,
        "breakdown": {
            "sentiment":   round(sentiment_pts),
            "stability":   round(stability_pts),
            "balance":     round(balance_pts),
            "actionability": round(action_pts),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def analyze_sentiment(
    segments:     List[Dict],
    action_count: int = 0,
) -> Dict[str, Any]:
    """
    Full sentiment analysis pipeline.

    Args:
        segments:     List of {speaker, start, end, text} dicts (from Whisper).
        action_count: Number of action items (used for health scoring).

    Returns:
        {
          overall:        {label, score, positive, negative, neutral},
          by_speaker:     {speaker_name: {label, score, positive, negative, neutral}},
          timeline:       [{segment_index, start, speaker, label, score,
                           positive, negative, neutral, smoothed_*}],
          meeting_score:  int  (0-100 legacy field),
          health:         {score, label, breakdown},
        }
    """
    if not segments:
        neutral = {"label": "neutral", "score": 0.5,
                   "positive": 0.0, "negative": 0.0, "neutral": 1.0}
        return {
            "overall": neutral, "by_speaker": {}, "timeline": [],
            "meeting_score": 50,
            "health": {"score": 50, "label": "Fair", "breakdown": {}},
        }

    # Filter out empty segments
    valid_segs  = [s for s in segments if s.get("text", "").strip()]
    texts       = [s["text"] for s in valid_segs]

    logger.info(f"Scoring sentiment for {len(valid_segs)} segments (batch mode)")
    scored = _batch_score_texts(texts)

    # Per-speaker buckets
    speaker_buckets: Dict[str, List[Dict]] = defaultdict(list)
    for seg, score in zip(valid_segs, scored):
        speaker_buckets[seg.get("speaker", "Speaker 1")].append(score)

    by_speaker = {spk: _aggregate(scores) for spk, scores in speaker_buckets.items()}
    overall    = _aggregate(scored)
    timeline   = _build_timeline(valid_segs, scored)
    health     = _compute_meeting_health(overall, by_speaker, timeline, action_count)

    # Legacy meeting_score field (kept for API backwards compat)
    meeting_score = health["score"]

    logger.info(
        f"Sentiment: overall={overall['label']} ({overall['score']:.2f}), "
        f"speakers={list(by_speaker)}, health={health['label']} ({health['score']})"
    )

    return {
        "overall":       overall,
        "by_speaker":    by_speaker,
        "timeline":      timeline,
        "meeting_score": meeting_score,
        "health":        health,
    }

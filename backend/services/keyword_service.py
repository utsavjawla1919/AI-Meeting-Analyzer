"""
services/keyword_service.py — Keyword enrichment and word cloud data generation.

Builds Chart.js / D3-compatible word cloud payloads from raw TF-IDF keywords,
adds POS tagging to classify noun/verb/adjective keywords,
and generates a co-occurrence matrix for topic graph visualisation.
"""

import re
import logging
from collections import Counter, defaultdict
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


# ── POS tagging ────────────────────────────────────────────────────────────────

def _pos_tag_keywords(keywords: List[Dict]) -> List[Dict]:
    """
    Tag each keyword with its dominant part of speech using NLTK.
    Adds a 'pos' field: NOUN | VERB | ADJ | OTHER.
    Falls back to 'NOUN' if NLTK unavailable.
    """
    try:
        import nltk
        try:
            nltk.data.find("taggers/averaged_perceptron_tagger")
        except LookupError:
            nltk.download("averaged_perceptron_tagger", quiet=True)

        words  = [k["word"].split()[0] for k in keywords]   # first token of bigrams
        tagged = nltk.pos_tag(words)

        pos_map = {
            "NN": "NOUN", "NNS": "NOUN", "NNP": "NOUN", "NNPS": "NOUN",
            "VB": "VERB", "VBD": "VERB", "VBG": "VERB",
            "VBN": "VERB", "VBP": "VERB", "VBZ": "VERB",
            "JJ": "ADJ",  "JJR": "ADJ",  "JJS": "ADJ",
        }

        enriched = []
        for kw, (_, tag) in zip(keywords, tagged):
            enriched.append({**kw, "pos": pos_map.get(tag, "OTHER")})
        return enriched

    except Exception as e:
        logger.warning(f"POS tagging failed ({e}) — defaulting to NOUN")
        return [{**k, "pos": "NOUN"} for k in keywords]


# ── Word cloud payload ─────────────────────────────────────────────────────────

def build_word_cloud_data(
    keywords: List[Dict],
    max_words: int = 60,
) -> List[Dict]:
    """
    Transform TF-IDF keywords into a word cloud dataset.

    Each item: { text, value, score, frequency, pos, color }

    `value` is normalized 10–100 (largest word = 100).
    Colors map to POS: NOUN=blue, VERB=green, ADJ=orange, OTHER=gray.
    """
    if not keywords:
        return []

    tagged = _pos_tag_keywords(keywords[:max_words])

    max_score = max(k["score"] for k in tagged) or 1.0
    max_freq  = max(k.get("frequency", 1) for k in tagged) or 1

    COLOR_MAP = {
        "NOUN":  "#3B82F6",  # blue
        "VERB":  "#10B981",  # green
        "ADJ":   "#F59E0B",  # amber
        "OTHER": "#94A3B8",  # slate
    }

    cloud_data = []
    for kw in tagged:
        # Blend TF-IDF score (70%) and frequency (30%) for visual size
        normalized = (kw["score"] / max_score) * 0.7 + \
                     (kw.get("frequency", 1) / max_freq) * 0.3
        value = round(10 + normalized * 90)   # 10–100 range

        cloud_data.append({
            "text":      kw["word"],
            "value":     value,
            "score":     kw["score"],
            "frequency": kw.get("frequency", 1),
            "pos":       kw.get("pos", "NOUN"),
            "color":     COLOR_MAP.get(kw.get("pos", "OTHER"), "#94A3B8"),
        })

    return sorted(cloud_data, key=lambda x: x["value"], reverse=True)


# ── Co-occurrence matrix ───────────────────────────────────────────────────────

def build_cooccurrence(
    full_text:   str,
    keywords:    List[Dict],
    window_size: int = 5,
    top_n:       int = 20,
) -> Dict[str, Any]:
    """
    Build a keyword co-occurrence matrix suitable for a D3 force graph.

    Args:
        full_text:   The full meeting transcript.
        keywords:    TF-IDF keyword list (word, score, frequency).
        window_size: Sliding word window for co-occurrence counting.
        top_n:       Only consider top N keywords.

    Returns:
        {
          nodes: [{id, label, weight}],
          edges: [{source, target, weight}],
        }
    """
    if not keywords or not full_text:
        return {"nodes": [], "edges": []}

    top_kws  = {k["word"].lower() for k in keywords[:top_n]}
    words    = re.findall(r"\b[a-z]{3,}\b", full_text.lower())
    cooccur: Dict[Tuple[str, str], int] = Counter()

    for i, word in enumerate(words):
        if word not in top_kws:
            continue
        window = words[i + 1: i + 1 + window_size]
        for other in window:
            if other in top_kws and other != word:
                pair = tuple(sorted([word, other]))
                cooccur[pair] += 1

    if not cooccur:
        return {"nodes": [], "edges": []}

    # Build node list (only include keywords that appear in at least one edge)
    connected_kws = set()
    for (a, b) in cooccur:
        connected_kws.add(a)
        connected_kws.add(b)

    kw_lookup = {k["word"].lower(): k for k in keywords}
    nodes = [
        {
            "id":     kw,
            "label":  kw.title(),
            "weight": kw_lookup.get(kw, {}).get("frequency", 1),
            "score":  round(kw_lookup.get(kw, {}).get("score", 0), 4),
        }
        for kw in connected_kws
    ]

    # Build edge list (filter weak co-occurrences)
    max_co = max(cooccur.values()) or 1
    edges = [
        {
            "source": a,
            "target": b,
            "weight": count,
            "strength": round(count / max_co, 3),
        }
        for (a, b), count in cooccur.most_common(60)
        if count >= 2
    ]

    logger.info(f"Co-occurrence graph: {len(nodes)} nodes, {len(edges)} edges")
    return {"nodes": nodes, "edges": edges}


# ── Topic timeline ─────────────────────────────────────────────────────────────

def build_topic_timeline(
    segments: List[Dict],
    topics:   List[Dict],
    interval_s: int = 60,
) -> List[Dict]:
    """
    Estimate which topic dominated each time interval of the meeting.
    Used for a "topic flow" timeline chart.

    Returns:
        [{time_start, time_end, dominant_topic, topic_scores: {label: score}}]
    """
    if not segments or not topics:
        return []

    topic_seeds = {t["label"]: t.get("keywords", []) for t in topics}
    total_dur   = max(s.get("end", 0) for s in segments)

    if total_dur <= 0:
        return []

    n_intervals = max(1, int(total_dur / interval_s))
    timeline    = []

    for i in range(n_intervals):
        t_start = i * interval_s
        t_end   = (i + 1) * interval_s

        # Collect text in this time window
        window_text = " ".join(
            s["text"] for s in segments
            if s.get("start", 0) >= t_start and s.get("start", 0) < t_end
        ).lower()

        if not window_text.strip():
            continue

        # Score each topic against window text
        topic_scores = {}
        for label, seeds in topic_seeds.items():
            hits = sum(window_text.count(seed) for seed in seeds)
            if hits:
                topic_scores[label] = hits

        dominant = max(topic_scores, key=topic_scores.get) if topic_scores else "General"

        timeline.append({
            "time_start":    t_start,
            "time_end":      t_end,
            "dominant_topic": dominant,
            "topic_scores":  topic_scores,
        })

    return timeline


# ── Public API ─────────────────────────────────────────────────────────────────

def enrich_keywords(
    full_text: str,
    keywords:  List[Dict],
    topics:    List[Dict],
    segments:  List[Dict],
) -> Dict[str, Any]:
    """
    Generate all keyword-related visual data in one call.

    Returns:
        {
          word_cloud:     [...],   # for word cloud component
          cooccurrence:   {...},   # nodes + edges for force graph
          topic_timeline: [...],   # topic flow over time
        }
    """
    word_cloud     = build_word_cloud_data(keywords)
    cooccurrence   = build_cooccurrence(full_text, keywords)
    topic_timeline = build_topic_timeline(segments, topics)

    logger.info(
        f"Keyword enrichment: {len(word_cloud)} cloud words, "
        f"{len(cooccurrence.get('edges', []))} co-edges, "
        f"{len(topic_timeline)} topic intervals"
    )

    return {
        "word_cloud":     word_cloud,
        "cooccurrence":   cooccurrence,
        "topic_timeline": topic_timeline,
    }

"""
services/nlp_service.py — NLP processing pipeline.

Stages:
  1. Text cleaning and sentence segmentation (NLTK)
  2. Named entity recognition (spaCy en_core_web_sm)
  3. TF-IDF keyword extraction (scikit-learn)
  4. Topic detection via keyword seed clustering
  5. Noun-chunk extraction for key phrase mining
  6. POS-based action verb detection
"""

import re
import logging
from collections import Counter
from typing import List, Dict, Any, Optional

from ai_pipeline import get_cached_model

logger = logging.getLogger(__name__)

# Entities we surface to the user
SURFACE_ENTITY_LABELS = {"PERSON", "ORG", "DATE", "GPE", "PRODUCT", "EVENT", "LOC", "MONEY"}

# Meeting-domain stop words (extend standard list)
CUSTOM_STOP_WORDS = {
    "um", "uh", "yeah", "yep", "okay", "ok", "like", "know", "right",
    "gonna", "wanna", "thing", "things", "actually", "basically", "literally",
    "kind", "sort", "mean", "really", "just", "also", "well", "lot", "bit",
    "good", "great", "nice", "sure", "think", "going", "make", "need", "want",
}

# Seed topics for clustering (extendable via config)
TOPIC_SEEDS: Dict[str, List[str]] = {
    "Project Planning":    ["project", "plan", "timeline", "milestone", "deadline", "roadmap", "sprint", "backlog"],
    "Budget & Finance":    ["budget", "cost", "revenue", "expense", "financial", "money", "spend", "roi", "profit"],
    "Product Development": ["feature", "product", "design", "user", "ux", "interface", "release", "launch", "mvp"],
    "Team & HR":           ["team", "hire", "employee", "resource", "onboard", "performance", "headcount", "role"],
    "Sales & Marketing":   ["sales", "marketing", "customer", "campaign", "lead", "conversion", "churn", "pipeline"],
    "Technical Discussion": ["code", "api", "database", "architecture", "infrastructure", "deploy", "bug", "fix", "test"],
    "Retrospective":       ["retrospective", "retro", "review", "feedback", "improve", "issue", "blocker", "lesson"],
    "Strategy":            ["strategy", "goal", "objective", "vision", "mission", "priority", "initiative", "okr"],
    "Customer Success":    ["support", "ticket", "client", "satisfaction", "nps", "feedback", "escalation", "sla"],
    "Data & Analytics":    ["data", "metric", "analytics", "report", "dashboard", "insight", "kpi", "trend"],
}


# ── Model loading ──────────────────────────────────────────────────────────────

def _get_spacy():
    def _load():
        import spacy
        try:
            return spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy en_core_web_sm not found — using blank English model")
            from spacy.lang.en import English
            return English()
    return get_cached_model("spacy:en_core_web_sm", _load)


def _ensure_nltk():
    import nltk
    for pkg, path in [
        ("punkt_tab",            "tokenizers/punkt_tab"),
        ("stopwords",            "corpora/stopwords"),
        ("averaged_perceptron_tagger", "taggers/averaged_perceptron_tagger"),
        ("vader_lexicon",        "sentiment/vader_lexicon"),
    ]:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(pkg, quiet=True)


# ── Text cleaning ──────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    text = re.sub(r"\b\w\b", " ", text)         # single-char words
    return text.strip()


def _get_stop_words() -> set:
    _ensure_nltk()
    from nltk.corpus import stopwords
    base = set(stopwords.words("english"))
    base.update(CUSTOM_STOP_WORDS)
    return base


# ── Sentence segmentation ──────────────────────────────────────────────────────

def _sentencize(text: str) -> List[str]:
    _ensure_nltk()
    import nltk
    try:
        return [s.strip() for s in nltk.sent_tokenize(text) if len(s.split()) >= 3]
    except Exception:
        return [s.strip() for s in re.split(r"[.!?]+", text) if len(s.split()) >= 3]


# ── Keyword extraction ─────────────────────────────────────────────────────────

def _extract_keywords(text: str, top_n: int = 25) -> List[Dict]:
    """TF-IDF + frequency keyword extraction."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    stop_words = _get_stop_words()
    sentences  = _sentencize(text)

    if len(sentences) < 2:
        sentences = [text]

    try:
        vec = TfidfVectorizer(
            max_features=300,
            stop_words=list(stop_words),
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )
        mat   = vec.fit_transform(sentences)
        names = vec.get_feature_names_out()
        scores = mat.sum(axis=0).A1

        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        freq  = Counter(w for w in words if w not in stop_words)

        keywords = sorted(
            [
                {
                    "word":      names[i],
                    "score":     round(float(scores[i]), 4),
                    "frequency": freq.get(names[i], 1),
                }
                for i in range(len(names))
                if scores[i] > 0
            ],
            key=lambda x: x["score"],
            reverse=True,
        )[:top_n]

    except Exception as e:
        logger.warning(f"TF-IDF failed ({e}) — falling back to frequency")
        words    = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        freq     = Counter(w for w in words if w not in stop_words)
        max_freq = max(freq.values(), default=1)
        keywords = [
            {"word": w, "score": round(c / max_freq, 4), "frequency": c}
            for w, c in freq.most_common(top_n)
        ]

    return keywords


# ── Named entity recognition ───────────────────────────────────────────────────

def _extract_entities(doc) -> List[Dict]:
    seen, entities = set(), []
    for ent in doc.ents:
        if ent.label_ not in SURFACE_ENTITY_LABELS:
            continue
        key = (ent.text.strip().lower(), ent.label_)
        if key in seen or len(ent.text.strip()) < 2:
            continue
        seen.add(key)
        entities.append({
            "text":  ent.text.strip(),
            "label": ent.label_,
            "type":  ent.label_.capitalize(),
        })
    return entities[:60]


# ── Noun chunk extraction ──────────────────────────────────────────────────────

def _extract_noun_chunks(doc, stop_words: set) -> List[str]:
    """Extract meaningful noun phrases for key-phrase mining."""
    chunks = []
    for chunk in doc.noun_chunks:
        text = chunk.text.strip().lower()
        words = text.split()
        if len(words) < 2:
            continue
        if all(w in stop_words for w in words):
            continue
        if len(text) > 50:
            continue
        chunks.append(chunk.text.strip())
    # Deduplicate while preserving order
    seen, result = set(), []
    for c in chunks:
        if c.lower() not in seen:
            seen.add(c.lower())
            result.append(c)
    return result[:30]


# ── Topic detection ────────────────────────────────────────────────────────────

def _detect_topics(text: str, keywords: List[Dict], top_n: int = 5) -> List[Dict]:
    """Score transcript against topic seed word lists."""
    text_lower = text.lower()
    kw_set     = {k["word"] for k in keywords}
    scored     = {}

    for topic, seeds in TOPIC_SEEDS.items():
        hits     = sum(text_lower.count(seed) for seed in seeds if seed in text_lower)
        kw_match = [s for s in seeds if s in kw_set]
        if hits > 0:
            confidence = round(min((hits / 15) * 0.7 + (len(kw_match) / len(seeds)) * 0.3, 1.0), 2)
            scored[topic] = {
                "label":      topic,
                "confidence": confidence,
                "keywords":   kw_match[:6],
                "hit_count":  hits,
            }

    topics = sorted(scored.values(), key=lambda x: x["confidence"], reverse=True)

    if not topics:
        top_kw = [k["word"] for k in keywords[:5]]
        topics = [{"label": "General Discussion", "confidence": 0.5,
                   "keywords": top_kw, "hit_count": 0}]

    return topics[:top_n]


# ── Key sentence extraction ────────────────────────────────────────────────────

def _extract_key_sentences(text: str, keywords: List[Dict], top_n: int = 8) -> List[str]:
    """
    Score each sentence by keyword density and return the most salient ones.
    Used for the 'key_points' field in the analysis document.
    """
    sentences = _sentencize(text)
    kw_set    = {k["word"].lower() for k in keywords[:20]}
    scored    = []

    for sent in sentences:
        words = sent.lower().split()
        if len(words) < 6:
            continue
        score = sum(1 for w in words if w in kw_set) / max(len(words), 1)
        # Boost sentences that contain decision/action language
        if re.search(r"\b(decided|agreed|will|must|should|action|next step)\b", sent, re.I):
            score *= 1.4
        scored.append((score, sent))

    scored.sort(key=lambda x: x[0], reverse=True)
    # Deduplicate near-identical sentences
    result = []
    for _, sent in scored:
        if not any(
            _similarity(sent, r) > 0.7
            for r in result
        ):
            result.append(sent)
        if len(result) >= top_n:
            break
    return result


def _similarity(a: str, b: str) -> float:
    """Simple Jaccard similarity for deduplication."""
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# ── Speaker-level stats ────────────────────────────────────────────────────────

def _compute_speaker_stats(segments: List[Dict]) -> Dict:
    """
    Compute per-speaker word counts and talk-time ratios.
    Useful for the analytics dashboard.
    """
    speaker_words: Dict[str, int] = Counter()
    speaker_time:  Dict[str, float] = Counter()

    for seg in segments:
        spk  = seg.get("speaker", "Unknown")
        text = seg.get("text", "")
        duration = max(0, seg.get("end", 0) - seg.get("start", 0))
        speaker_words[spk] += len(text.split())
        speaker_time[spk]  += duration

    total_time  = sum(speaker_time.values()) or 1
    total_words = sum(speaker_words.values()) or 1

    return {
        spk: {
            "word_count":    speaker_words[spk],
            "talk_time":     round(speaker_time[spk], 1),
            "word_pct":      round(speaker_words[spk] / total_words * 100, 1),
            "time_pct":      round(speaker_time[spk]  / total_time  * 100, 1),
        }
        for spk in set(list(speaker_words) + list(speaker_time))
    }


# ── Public API ─────────────────────────────────────────────────────────────────

def process_nlp(full_text: str, segments: List[Dict]) -> Dict[str, Any]:
    """
    Full NLP processing pipeline.

    Returns:
      { keywords, entities, topics, key_sentences, noun_chunks,
        speaker_stats, sentence_count, word_count }
    """
    if not full_text or not full_text.strip():
        return {
            "keywords": [], "entities": [], "topics": [],
            "key_sentences": [], "noun_chunks": [],
            "speaker_stats": {}, "sentence_count": 0, "word_count": 0,
        }

    text      = _clean_text(full_text)
    nlp       = _get_spacy()
    stop_words = _get_stop_words()

    # spaCy doc (cap at 100k chars — larger texts get truncated for perf)
    doc = nlp(text[:100_000])

    keywords      = _extract_keywords(text)
    entities      = _extract_entities(doc)
    topics        = _detect_topics(text, keywords)
    key_sentences = _extract_key_sentences(text, keywords)
    noun_chunks   = _extract_noun_chunks(doc, stop_words)
    speaker_stats = _compute_speaker_stats(segments)
    sentences     = _sentencize(text)

    logger.info(
        f"NLP: {len(keywords)} kw, {len(entities)} ents, "
        f"{len(topics)} topics, {len(segments)} segs"
    )

    return {
        "keywords":       keywords,
        "entities":       entities,
        "topics":         topics,
        "key_sentences":  key_sentences,
        "noun_chunks":    noun_chunks,
        "speaker_stats":  speaker_stats,
        "sentence_count": len(sentences),
        "word_count":     len(text.split()),
    }

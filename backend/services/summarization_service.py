"""
services/summarization_service.py — Meeting summarization & extraction pipeline.

Stages:
  1. Abstractive summary      (HuggingFace BART-large-CNN or T5)
  2. Action item extraction   (regex + dependency parse patterns)
  3. Decision extraction      (keyword + syntactic patterns)
  4. Key point ranking        (TF-IDF sentence scoring)
  5. AI title generation      (summary + keyword fusion)
  6. Smart recommendations    (rule-based from meeting content)
  7. Meeting productivity score (0-100 composite metric)
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple

from ai_pipeline import get_cached_model

logger = logging.getLogger(__name__)

# ─── Model sizes that fit comfortably on CPU ──────────────────────────────────
SUMMARIZER_MAX_INPUT_TOKENS = 1024   # BART context window
CHUNK_WORD_LIMIT            = 700    # words per chunk fed to summarizer


# ══════════════════════════════════════════════════════════════════════════════
# MODEL LOADING
# ══════════════════════════════════════════════════════════════════════════════

def _get_summarizer(model_name: str = "facebook/bart-large-cnn"):
    def _load():
        from transformers import pipeline
        logger.info(f"Loading summarization model: {model_name}")
        return pipeline(
            "summarization",
            model=model_name,
            device=-1,          # -1 = CPU; 0 = first GPU
            truncation=True,
        )
    return get_cached_model(f"summarizer:{model_name}", _load)


# ══════════════════════════════════════════════════════════════════════════════
# ABSTRACTIVE SUMMARIZATION
# ══════════════════════════════════════════════════════════════════════════════

def _split_into_chunks(text: str, max_words: int = CHUNK_WORD_LIMIT) -> List[str]:
    """Split transcript into model-friendly chunks at sentence boundaries."""
    sentence_re = re.compile(r"(?<=[.!?])\s+")
    sentences   = sentence_re.split(text)
    chunks, cur_chunk, cur_count = [], [], 0

    for sent in sentences:
        wc = len(sent.split())
        if cur_count + wc > max_words and cur_chunk:
            chunks.append(" ".join(cur_chunk))
            cur_chunk  = [sent]
            cur_count  = wc
        else:
            cur_chunk.append(sent)
            cur_count += wc

    if cur_chunk:
        chunks.append(" ".join(cur_chunk))

    return chunks or [text]


def _run_summarizer(pipe, text: str) -> str:
    """Run a single HuggingFace summarization call with safe length bounds."""
    word_count = len(text.split())
    max_len    = min(180, max(40, word_count // 4))
    min_len    = min(30, max_len - 10)

    try:
        result = pipe(
            text,
            max_length=max_len,
            min_length=min_len,
            do_sample=False,
            truncation=True,
            no_repeat_ngram_size=3,
        )
        return result[0]["summary_text"].strip()
    except Exception as e:
        logger.warning(f"Summarizer call failed ({e}) — using extractive fallback")
        return _extractive_fallback(text, n_sentences=3)


def _extractive_fallback(text: str, n_sentences: int = 5) -> str:
    """Return the first N meaningful sentences as a simple extractive summary."""
    sents = re.split(r"(?<=[.!?])\s+", text)
    sents = [s.strip() for s in sents if len(s.split()) >= 6]
    return " ".join(sents[:n_sentences])


def generate_summary(text: str, model_name: str = "facebook/bart-large-cnn") -> str:
    """
    Generate an abstractive meeting summary.
    Handles long transcripts by chunking, summarizing each chunk,
    then doing a second-pass summary of the combined chunk summaries.
    """
    word_count = len(text.split())
    logger.info(f"Summarizing {word_count} words with {model_name}")

    if word_count < 80:
        return text[:600]

    try:
        pipe   = _get_summarizer(model_name)
        chunks = _split_into_chunks(text)

        chunk_summaries = [_run_summarizer(pipe, chunk) for chunk in chunks]
        combined = " ".join(chunk_summaries)

        # Second pass if multi-chunk
        if len(chunks) > 1 and len(combined.split()) > 200:
            final = _run_summarizer(pipe, combined)
        else:
            final = combined

        logger.info(f"Summary: {len(final.split())} words from {len(chunks)} chunk(s)")
        return final

    except Exception as e:
        logger.error(f"Summarization failed entirely ({e}) — extractive fallback")
        return _extractive_fallback(text)


# ══════════════════════════════════════════════════════════════════════════════
# ACTION ITEM EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

# Ordered from highest to lowest precision
ACTION_PATTERNS: List[Tuple[str, str]] = [
    # "John will send the report by Friday"
    (r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+(?:will|is going to|needs? to|has to)\s+([^.!?\n]{8,100})",
     "assignee_verb"),
    # "Action item: update the roadmap"
    (r"(?:action item|todo|to-do|follow.?up|task|next step)[:\s]+([^.!?\n]{8,120})",
     "labeled"),
    # "we need to / should / must schedule a demo"
    (r"(?:we|the team)\s+(?:need to|should|must|have to|will)\s+([^.!?\n]{8,100})",
     "team_obligation"),
    # "please send / review / complete ..."
    (r"(?:please|can you|could you)\s+([^.!?\n]{8,80})",
     "request"),
    # "by [date] ..."
    (r"by\s+(?:next\s+\w+|tomorrow|end of\s+\w+|EOD|[A-Z][a-z]+\s+\d{1,2})[,:\s]+([^.!?\n]{8,100})",
     "deadline"),
    # "assigned to / owner: ..."
    (r"(?:assigned to|owner|responsible)[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)[,\s]+(?:to\s+)?([^.!?\n]{8,100})",
     "assignment"),
]

PRIORITY_HIGH = re.compile(
    r"\b(urgent|asap|immediately|critical|blocker|high priority|p0|p1)\b", re.I
)
PRIORITY_LOW = re.compile(
    r"\b(eventually|backlog|nice to have|low priority|when possible|someday)\b", re.I
)

DATE_RE = re.compile(
    r"\b(by\s+)?"
    r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|tomorrow|next week|end of day|EOD|end of month|EOM"
    r"|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?"
    r"|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"(\s+\d{1,2}(?:st|nd|rd|th)?)?",
    re.I,
)

PERSON_RE = re.compile(r"\b([A-Z][a-z]{1,20}(?:\s[A-Z][a-z]{1,20})?)\b")


def _extract_action_items(text: str) -> List[Dict]:
    seen, actions = set(), []

    for pattern, pattern_type in ACTION_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            groups = match.groups()

            # Build item text from match groups
            if pattern_type == "assignee_verb":
                assignee_candidate = groups[0]
                item_text = f"{groups[0]} {match.group(0).split(groups[0], 1)[1].strip()}"
            elif pattern_type == "assignment":
                assignee_candidate = groups[0]
                item_text = groups[1].strip()
            else:
                assignee_candidate = None
                item_text = groups[-1].strip()

            item_text = re.sub(r"\s+", " ", item_text).rstrip(".,;:").strip()

            if len(item_text.split()) < 3:
                continue
            key = item_text.lower()[:60]
            if key in seen:
                continue
            seen.add(key)

            # Priority detection
            if PRIORITY_HIGH.search(item_text):
                priority = "high"
            elif PRIORITY_LOW.search(item_text):
                priority = "low"
            else:
                priority = "medium"

            # Due date detection
            due_match = DATE_RE.search(item_text)
            due_date  = due_match.group(0).strip() if due_match else None

            # Assignee: prefer explicit, fall back to first capitalized name
            assignee = assignee_candidate
            if not assignee:
                person_match = PERSON_RE.search(item_text)
                # Ignore common false positives
                if person_match and person_match.group(1) not in {
                    "The", "We", "Our", "This", "That", "It", "They"
                }:
                    assignee = person_match.group(1)

            actions.append({
                "text":         item_text,
                "assignee":     assignee,
                "due_date":     due_date,
                "priority":     priority,
                "pattern_type": pattern_type,
            })

    # Sort: high priority first, then by order of appearance
    priority_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda x: priority_order.get(x["priority"], 1))

    # Remove internal debug field before returning
    for a in actions:
        a.pop("pattern_type", None)

    return actions[:15]


# ══════════════════════════════════════════════════════════════════════════════
# DECISION EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

DECISION_PATTERNS: List[str] = [
    r"(?:we decided|we agreed|it was decided|decision made?)[:\s]+([^.!?\n]{10,160})",
    r"(?:agreed to|decided to|resolved to|concluded to)\s+([^.!?\n]{10,140})",
    r"(?:the team|everyone|all)\s+(?:agreed|decided|approved|confirmed)\s+(?:to\s+)?([^.!?\n]{10,140})",
    r"(?:going forward|moving forward)[,\s]+(?:we will\s+)?([^.!?\n]{10,140})",
    r"(?:go ahead with|approved[:\s]+|signed off on)\s+([^.!?\n]{10,140})",
    r"(?:consensus was|conclusion)[:\s]+([^.!?\n]{10,140})",
    r"(?:final decision|final answer)[:\s]+([^.!?\n]{10,140})",
]


def _extract_decisions(text: str) -> List[Dict]:
    seen, decisions = set(), []

    for pattern in DECISION_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            item = match.group(1).strip().rstrip(".,;")
            if len(item.split()) < 4:
                continue
            key = item.lower()[:60]
            if key in seen:
                continue
            seen.add(key)

            # Grab surrounding sentence as context
            start   = max(0, match.start() - 80)
            context = text[start: match.start()].strip()
            context = re.sub(r"\s+", " ", context)[-80:].strip()

            decisions.append({
                "text":    item,
                "context": context or None,
            })

    return decisions[:12]


# ══════════════════════════════════════════════════════════════════════════════
# KEY POINTS RANKING
# ══════════════════════════════════════════════════════════════════════════════

def _rank_key_points(text: str, keywords: List[Dict], n: int = 8) -> List[str]:
    """
    Score every sentence by TF-IDF keyword density + structural signals
    (starts with a name, contains decision language, etc.)
    Return the top N as key discussion points.
    """
    sents  = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) >= 6]
    kw_set = {k["word"].lower() for k in keywords[:25]}

    def score(sent: str) -> float:
        words = sent.lower().split()
        kw_hits = sum(1 for w in words if w in kw_set)
        density = kw_hits / max(len(words), 1)

        bonus = 0.0
        if re.search(r"\b(decided|agreed|will|action|next|key|important|critical)\b", sent, re.I):
            bonus += 0.15
        if re.search(r"^[A-Z][a-z]+\s", sent):    # starts with a name
            bonus += 0.05
        if 10 <= len(words) <= 35:                 # ideal sentence length
            bonus += 0.05

        return density + bonus

    scored = sorted(((score(s), s) for s in sents), reverse=True)

    # Deduplicate using Jaccard
    result = []
    for _, sent in scored:
        if not any(_jaccard(sent, r) > 0.55 for r in result):
            result.append(sent)
        if len(result) >= n:
            break

    return result


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.lower().split()), set(b.lower().split())
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0


# ══════════════════════════════════════════════════════════════════════════════
# AI TITLE GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def _generate_ai_title(summary: str, keywords: List[Dict], topics: List[Dict]) -> str:
    """
    Generate a concise, descriptive meeting title using:
    1. First coherent sentence of the summary (if 4–10 words)
    2. Top topic + top keyword fusion
    3. Generic fallback
    """
    # Strategy 1: clean first sentence of summary
    first = re.split(r"[.!?]", summary)[0].strip()
    words = first.split()
    if 4 <= len(words) <= 12:
        # Remove leading filler words
        filler = {"the", "this", "a", "an", "in", "at", "on", "for", "of"}
        while words and words[0].lower() in filler:
            words.pop(0)
        if 4 <= len(words) <= 12:
            return " ".join(words).rstrip(".,;:")

    # Strategy 2: topic + keyword
    top_topic  = topics[0]["label"]   if topics   else None
    top_kw     = keywords[0]["word"].title() if keywords else None

    if top_topic and top_kw:
        return f"{top_topic}: {top_kw}"
    if top_topic:
        return f"Meeting — {top_topic}"
    if top_kw:
        kws = ", ".join(k["word"].title() for k in keywords[:3])
        return f"Team Meeting: {kws}"

    return "Team Meeting"


# ══════════════════════════════════════════════════════════════════════════════
# SMART RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _generate_recommendations(
    action_items:  List[Dict],
    decisions:     List[Dict],
    key_points:    List[str],
    speaker_stats: Dict,
    sentiment:     str = "neutral",
) -> List[str]:
    """
    Rule-based smart recommendations tailored to the meeting's content.
    """
    recs = []

    # Action item quality
    if len(action_items) == 0:
        recs.append(
            "No clear action items were detected. Consider sending a follow-up email "
            "with explicit tasks and owners."
        )
    elif len(action_items) > 8:
        recs.append(
            f"{len(action_items)} action items were identified — consider prioritizing "
            "the top 3 to keep the team focused."
        )

    unassigned = [a for a in action_items if not a.get("assignee")]
    if unassigned:
        recs.append(
            f"{len(unassigned)} action item(s) have no assigned owner. "
            "Assign responsibility to improve accountability."
        )

    no_due_date = [a for a in action_items if not a.get("due_date")]
    if len(no_due_date) > 2:
        recs.append("Add due dates to action items to create a concrete timeline.")

    # Decisions
    if len(decisions) == 0 and len(action_items) > 0:
        recs.append(
            "Action items were captured but no formal decisions were recorded. "
            "Confirm alignment with all stakeholders."
        )

    # Speaker balance
    if speaker_stats:
        times = [v["time_pct"] for v in speaker_stats.values()]
        if times and max(times) > 70:
            dominant = max(speaker_stats, key=lambda k: speaker_stats[k]["time_pct"])
            recs.append(
                f"{dominant} spoke for over 70% of the meeting. "
                "Consider round-robin check-ins to improve participation."
            )

    # Sentiment
    if sentiment == "negative":
        recs.append(
            "The overall meeting tone was negative. Consider a brief team retrospective "
            "to surface blockers and low morale."
        )

    # Always-on recommendations
    recs.append("Share this AI-generated summary with all participants within 24 hours.")
    if len(action_items) > 0:
        recs.append("Schedule a 15-minute follow-up to track action item progress.")

    return recs[:5]


# ══════════════════════════════════════════════════════════════════════════════
# PRODUCTIVITY SCORE
# ══════════════════════════════════════════════════════════════════════════════

def _compute_productivity_score(
    action_items: List[Dict],
    decisions:    List[Dict],
    key_points:   List[str],
    sentiment:    str = "neutral",
    duration_s:   int = 0,
) -> int:
    """
    0-100 composite meeting productivity score.

    Factors:
      - Action items present and assigned      (0–25 pts)
      - Decisions captured                     (0–20 pts)
      - Key discussion points identified       (0–15 pts)
      - Positive / neutral sentiment           (0–20 pts)
      - Efficient duration (15–60 min optimal) (0–20 pts)
    """
    score = 0

    # Action items (25 pts max)
    n_actions  = len(action_items)
    assigned   = sum(1 for a in action_items if a.get("assignee"))
    score += min(n_actions * 4, 16)           # up to 16 for having actions
    score += min(assigned   * 3, 9)           # up to 9 for assigning them

    # Decisions (20 pts max)
    score += min(len(decisions) * 5, 20)

    # Key points (15 pts max)
    score += min(len(key_points) * 2, 15)

    # Sentiment (20 pts max)
    sentiment_pts = {"positive": 20, "neutral": 14, "negative": 6}
    score += sentiment_pts.get(sentiment, 14)

    # Duration efficiency (20 pts max)
    if duration_s > 0:
        minutes = duration_s / 60
        if 15 <= minutes <= 60:
            score += 20       # ideal range
        elif 5 <= minutes < 15:
            score += 12       # too short
        elif 60 < minutes <= 90:
            score += 10       # getting long
        else:
            score += 4        # too long or unknown

    return min(100, score)


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def summarize_and_extract(
    full_text:    str,
    keywords:     List[Dict],
    topics:       Optional[List[Dict]] = None,
    speaker_stats: Optional[Dict]      = None,
    sentiment:    str                  = "neutral",
    duration_s:   int                  = 0,
    model_name:   str                  = "facebook/bart-large-cnn",
) -> Dict[str, Any]:
    """
    Master extraction function. Returns:
      { summary, ai_title, action_items, decisions, key_points,
        recommendations, productivity_score }
    """
    if not full_text or not full_text.strip():
        return {
            "summary": "", "ai_title": "Meeting",
            "action_items": [], "decisions": [],
            "key_points": [], "recommendations": [],
            "productivity_score": 0,
        }

    topics        = topics        or []
    speaker_stats = speaker_stats or {}

    logger.info(f"Extraction pipeline: {len(full_text.split())} words")

    summary      = generate_summary(full_text, model_name)
    action_items = _extract_action_items(full_text)
    decisions    = _extract_decisions(full_text)
    key_points   = _rank_key_points(full_text, keywords)
    ai_title     = _generate_ai_title(summary, keywords, topics)
    recommendations = _generate_recommendations(
        action_items, decisions, key_points, speaker_stats, sentiment
    )
    productivity_score = _compute_productivity_score(
        action_items, decisions, key_points, sentiment, duration_s
    )

    logger.info(
        f"Extraction done: {len(action_items)} actions, {len(decisions)} decisions, "
        f"score={productivity_score}"
    )

    return {
        "summary":            summary,
        "ai_title":           ai_title,
        "action_items":       action_items,
        "decisions":          decisions,
        "key_points":         key_points,
        "recommendations":    recommendations,
        "productivity_score": productivity_score,
    }

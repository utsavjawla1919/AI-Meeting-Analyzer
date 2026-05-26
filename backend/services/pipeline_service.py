"""
services/pipeline_service.py — Master AI pipeline orchestrator.

Called in a background thread after every meeting upload.
Uses PipelineProgress for granular per-stage status updates
so the frontend can poll and show a live progress bar.

Full pipeline:
  Stage 1 — Speech-to-Text        (Whisper + audio extraction)
  Stage 2 — NLP Processing        (spaCy + NLTK + TF-IDF)
  Stage 3 — Summarization         (BART/T5 + rule-based extraction)
  Stage 4 — Sentiment Analysis    (DistilBERT + VADER)
  Stage 5 — Persist + finalise    (MongoDB writes)
"""

import logging
import traceback
from typing import Optional

logger = logging.getLogger(__name__)


def run_pipeline(app, meeting_id: str, file_path: str) -> None:
    """
    Entry point invoked from a daemon thread.
    Wraps _execute() in an app context so Flask globals (db, config) work.
    """
    with app.app_context():
        try:
            _execute(app.db, app.config, meeting_id, file_path)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error(f"[Pipeline:{meeting_id}] Fatal error:\n{tb}")
            from models.models import MeetingModel
            MeetingModel.set_status(app.db, meeting_id, "failed", str(exc)[:500])


def _execute(db, config: dict, meeting_id: str, file_path: str) -> None:
    """
    Runs all pipeline stages sequentially, updating MongoDB after each one.
    On any stage failure the error is recorded and the pipeline aborts.
    """
    from ai_pipeline.progress import PipelineProgress
    from models.models import (
        MeetingModel, TranscriptModel, AnalysisModel, utcnow,
    )
    from bson import ObjectId

    progress = PipelineProgress(db, meeting_id)
    progress.set_overall_status("transcribing")

    # ── Retrieve meeting to get stored metadata ────────────────────────────────
    meeting    = MeetingModel.find_by_id(db, meeting_id)
    duration_s = meeting.get("duration_seconds", 0) or 0


    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 1 — SPEECH-TO-TEXT
    # ══════════════════════════════════════════════════════════════════════════
    with progress.stage("transcription", "Speech-to-Text (Whisper)"):
        from services.stt_service import transcribe_audio

        stt = transcribe_audio(
            file_path=file_path,
            model_name=config.get("WHISPER_MODEL", "base"),
            enable_diarization=True,
        )

        full_text  = stt["full_text"]
        segments   = stt["segments"]
        language   = stt["language"]
        duration_s = stt.get("duration_seconds", duration_s)

        # Persist transcript document
        TranscriptModel.create(
            db=db,
            meeting_id=meeting_id,
            full_text=full_text,
            segments=segments,
            language=language,
        )

        # Update meeting with real duration + language
        db.meetings.update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": {
                "language":         language,
                "duration_seconds": duration_s,
                "updated_at":       utcnow(),
            }},
        )
        logger.info(
            f"[{meeting_id}] STT: {stt['word_count']} words, "
            f"{len(segments)} segments, lang={language}, "
            f"silence={stt['silence_ratio']:.1%}"
        )

    # Guard: abort if transcript is empty
    if not full_text or not full_text.strip():
        raise ValueError(
            "Transcript is empty — the recording may contain no audible speech."
        )


    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 2 — NLP PROCESSING
    # ══════════════════════════════════════════════════════════════════════════
    progress.set_overall_status("analyzing")

    with progress.stage("nlp", "NLP (keywords, entities, topics)"):
        from services.nlp_service import process_nlp

        nlp = process_nlp(full_text=full_text, segments=segments)

        AnalysisModel.update(db, meeting_id, {
            "keywords":      nlp["keywords"],
            "entities":      nlp["entities"],
            "topics":        nlp["topics"],
            "key_points":    nlp["key_sentences"],
            "noun_chunks":   nlp.get("noun_chunks", []),
            "speaker_stats": nlp.get("speaker_stats", {}),
        })
        logger.info(
            f"[{meeting_id}] NLP: {len(nlp['keywords'])} kw, "
            f"{len(nlp['entities'])} ents, {len(nlp['topics'])} topics"
        )


    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 3 — SUMMARIZATION + EXTRACTION
    # ══════════════════════════════════════════════════════════════════════════
    with progress.stage("summarization", "Summarization & Extraction"):
        from services.summarization_service import summarize_and_extract

        extraction = summarize_and_extract(
            full_text=full_text,
            keywords=nlp["keywords"],
            topics=nlp["topics"],
            speaker_stats=nlp.get("speaker_stats", {}),
            sentiment="neutral",           # placeholder; updated after Stage 4
            duration_s=duration_s,
            model_name=config.get("SUMMARIZER_MODEL", "facebook/bart-large-cnn"),
        )

        AnalysisModel.update(db, meeting_id, {
            "summary":            extraction["summary"],
            "ai_title":           extraction["ai_title"],
            "action_items":       extraction["action_items"],
            "decisions":          extraction["decisions"],
            "key_points":         extraction["key_points"],
            "recommendations":    extraction["recommendations"],
            "meeting_score":      extraction["productivity_score"],
        })

        # Write AI title back to the meeting document too
        db.meetings.update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": {"ai_title": extraction["ai_title"], "updated_at": utcnow()}},
        )
        logger.info(
            f"[{meeting_id}] Extraction: '{extraction['ai_title']}', "
            f"{len(extraction['action_items'])} actions, "
            f"{len(extraction['decisions'])} decisions"
        )


    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 4 — SENTIMENT ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    with progress.stage("sentiment", "Sentiment Analysis"):
        from services.sentiment_service import analyze_sentiment

        sentiment = analyze_sentiment(
            segments=segments,
            action_count=len(extraction["action_items"]),
        )

        AnalysisModel.update(db, meeting_id, {
            "sentiment_overall":    sentiment["overall"],
            "sentiment_by_speaker": sentiment["by_speaker"],
            "sentiment_timeline":   sentiment["timeline"],
            "meeting_score":        sentiment["meeting_score"],
            "health":               sentiment.get("health", {}),
        })

        # Re-compute productivity score now that we have real sentiment
        final_score = _recompute_score(extraction, sentiment)
        AnalysisModel.update(db, meeting_id, {"meeting_score": final_score})

        # Update recommendations with real sentiment
        from services.summarization_service import _generate_recommendations
        updated_recs = _generate_recommendations(
            extraction["action_items"],
            extraction["decisions"],
            extraction["key_points"],
            nlp.get("speaker_stats", {}),
            sentiment["overall"]["label"],
        )
        AnalysisModel.update(db, meeting_id, {"recommendations": updated_recs})

        logger.info(
            f"[{meeting_id}] Sentiment: {sentiment['overall']['label']} "
            f"({sentiment['overall']['score']:.2f}), "
            f"health={sentiment['health']['label']} ({sentiment['health']['score']})"
        )


    # ══════════════════════════════════════════════════════════════════════════
    # DONE
    # ══════════════════════════════════════════════════════════════════════════
    progress.set_overall_status("completed")

    timings = progress.get_timings()
    total   = sum(timings.values())
    logger.info(
        f"[{meeting_id}] Pipeline complete in {total:.1f}s | "
        + " | ".join(f"{k}={v:.1f}s" for k, v in timings.items())
    )

    # Store timing metadata on the analysis document
    AnalysisModel.update(db, meeting_id, {
        "pipeline_timings":    timings,
        "pipeline_total_secs": round(total, 1),
    })


def _recompute_score(extraction: dict, sentiment: dict) -> int:
    """
    Final productivity score combining extraction metrics + real sentiment.
    Overrides the placeholder used during Stage 3.
    """
    from services.summarization_service import _compute_productivity_score
    return _compute_productivity_score(
        action_items=extraction["action_items"],
        decisions=extraction["decisions"],
        key_points=extraction["key_points"],
        sentiment=sentiment["overall"]["label"],
        duration_s=0,  # already factored into stage 3 score
    )

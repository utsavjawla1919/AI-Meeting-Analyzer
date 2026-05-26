"""
Analysis Controller — retrieve AI analysis results, retry failed jobs,
and expose individual result sub-sections (sentiment, keywords, etc.)
"""

from flask import request, jsonify, current_app, g
import logging

from models.models import MeetingModel, TranscriptModel, AnalysisModel
from middleware.auth_middleware import verify_meeting_ownership
from utils.serializer import serialize_doc

logger = logging.getLogger(__name__)


def get_analysis(meeting_id: str):
    """
    GET /api/analysis/<meeting_id>
    Returns the complete analysis document for a meeting.
    """
    if not verify_meeting_ownership(meeting_id):
        return jsonify({"error": "Not found or access denied"}), 404

    analysis = AnalysisModel.find_by_meeting(current_app.db, meeting_id)
    if not analysis:
        return jsonify({"error": "Analysis not yet available"}), 404

    meeting = MeetingModel.find_by_id(current_app.db, meeting_id)

    return jsonify({
        "analysis": serialize_doc(analysis),
        "status":   meeting["status"],
    }), 200


def get_transcript(meeting_id: str):
    """
    GET /api/analysis/<meeting_id>/transcript
    Returns the timestamped transcript with speaker labels.
    """
    if not verify_meeting_ownership(meeting_id):
        return jsonify({"error": "Not found or access denied"}), 404

    transcript = TranscriptModel.find_by_meeting(current_app.db, meeting_id)
    if not transcript:
        return jsonify({"error": "Transcript not yet available"}), 404

    return jsonify({"transcript": serialize_doc(transcript)}), 200


def get_sentiment(meeting_id: str):
    """
    GET /api/analysis/<meeting_id>/sentiment
    Returns overall, per-speaker, and timeline sentiment data (for Chart.js).
    """
    if not verify_meeting_ownership(meeting_id):
        return jsonify({"error": "Not found or access denied"}), 404

    analysis = AnalysisModel.find_by_meeting(current_app.db, meeting_id)
    if not analysis:
        return jsonify({"error": "Analysis not available"}), 404

    return jsonify({
        "overall":    analysis.get("sentiment_overall", {}),
        "by_speaker": analysis.get("sentiment_by_speaker", {}),
        "timeline":   analysis.get("sentiment_timeline", []),
    }), 200


def get_action_items(meeting_id: str):
    """
    GET /api/analysis/<meeting_id>/actions
    Returns extracted action items and decisions.
    """
    if not verify_meeting_ownership(meeting_id):
        return jsonify({"error": "Not found or access denied"}), 404

    analysis = AnalysisModel.find_by_meeting(current_app.db, meeting_id)
    if not analysis:
        return jsonify({"error": "Analysis not available"}), 404

    return jsonify({
        "action_items": analysis.get("action_items", []),
        "decisions":    analysis.get("decisions", []),
        "key_points":   analysis.get("key_points", []),
    }), 200


def get_keywords(meeting_id: str):
    """
    GET /api/analysis/<meeting_id>/keywords
    Returns keywords, topics, and named entities.
    """
    if not verify_meeting_ownership(meeting_id):
        return jsonify({"error": "Not found or access denied"}), 404

    analysis = AnalysisModel.find_by_meeting(current_app.db, meeting_id)
    if not analysis:
        return jsonify({"error": "Analysis not available"}), 404

    return jsonify({
        "keywords": analysis.get("keywords", []),
        "topics":   analysis.get("topics", []),
        "entities": analysis.get("entities", []),
    }), 200


def retry_analysis(meeting_id: str):
    """
    POST /api/analysis/<meeting_id>/retry
    Re-triggers the AI pipeline for a failed meeting.
    """
    if not verify_meeting_ownership(meeting_id):
        return jsonify({"error": "Not found or access denied"}), 404

    meeting = MeetingModel.find_by_id(current_app.db, meeting_id)
    if meeting["status"] not in ("failed", "completed"):
        return jsonify({"error": "Can only retry failed or completed meetings"}), 400

    if not meeting.get("file_path"):
        return jsonify({"error": "Original file no longer available"}), 410

    # Reset state
    MeetingModel.set_status(current_app.db, meeting_id, "pending")
    MeetingModel.set_stage(current_app.db, meeting_id, "transcription", "pending")
    MeetingModel.set_stage(current_app.db, meeting_id, "nlp", "pending")
    MeetingModel.set_stage(current_app.db, meeting_id, "summarization", "pending")
    MeetingModel.set_stage(current_app.db, meeting_id, "sentiment", "pending")

    import threading
    from services.pipeline_service import run_pipeline
    thread = threading.Thread(
        target=run_pipeline,
        args=(current_app._get_current_object(), meeting_id, meeting["file_path"]),
        daemon=True,
    )
    thread.start()

    logger.info(f"Retry pipeline started for meeting {meeting_id}")
    return jsonify({"message": "Analysis restarted"}), 200


def search_meetings():
    """
    GET /api/analysis/search?q=<query>&field=<all|transcript|summary|keywords>
    Full-text search across all of the user's meetings.
    """
    from bson import ObjectId

    query  = request.args.get("q", "").strip()
    field  = request.args.get("field", "all")
    page   = max(1, int(request.args.get("page", 1)))
    limit  = min(int(request.args.get("limit", 10)), 50)

    if not query:
        return jsonify({"error": "Search query is required"}), 400

    uid = ObjectId(g.current_user_id)

    # Get user's meeting IDs first
    meeting_ids = [
        m["_id"]
        for m in current_app.db.meetings.find(
            {"user_id": uid, "is_deleted": False}, {"_id": 1}
        )
    ]

    results = []

    # Search transcripts
    if field in ("all", "transcript"):
        trans_cursor = current_app.db.transcripts.find(
            {
                "meeting_id": {"$in": meeting_ids},
                "full_text":  {"$regex": query, "$options": "i"},
            },
            {"meeting_id": 1, "full_text": 1},
        )
        for t in trans_cursor:
            meeting = MeetingModel.find_by_id(current_app.db, str(t["meeting_id"]))
            if meeting:
                # Snippet extraction — 150 chars around first match
                text  = t["full_text"]
                idx   = text.lower().find(query.lower())
                start = max(0, idx - 75)
                snippet = ("…" if start > 0 else "") + text[start:start + 150] + "…"
                results.append({
                    "meeting_id":   str(t["meeting_id"]),
                    "meeting_title": meeting.get("title", ""),
                    "match_type":   "transcript",
                    "snippet":      snippet,
                })

    # Search summaries / action items
    if field in ("all", "summary"):
        ana_cursor = current_app.db.analyses.find(
            {
                "meeting_id": {"$in": meeting_ids},
                "$or": [
                    {"summary":     {"$regex": query, "$options": "i"}},
                    {"ai_title":    {"$regex": query, "$options": "i"}},
                    {"key_points":  {"$regex": query, "$options": "i"}},
                ],
            },
            {"meeting_id": 1, "summary": 1, "ai_title": 1},
        )
        seen = {r["meeting_id"] for r in results}
        for a in ana_cursor:
            mid = str(a["meeting_id"])
            if mid in seen:
                continue
            meeting = MeetingModel.find_by_id(current_app.db, mid)
            if meeting:
                results.append({
                    "meeting_id":    mid,
                    "meeting_title": meeting.get("title", ""),
                    "match_type":    "summary",
                    "snippet":       (a.get("summary") or "")[:150] + "…",
                })

    # Paginate results
    total      = len(results)
    paginated  = results[(page - 1) * limit: page * limit]

    return jsonify({
        "results": paginated,
        "total":   total,
        "page":    page,
        "limit":   limit,
    }), 200

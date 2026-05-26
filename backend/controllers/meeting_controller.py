"""
Meeting Controller — file upload, CRUD, and status management.
File validation, storage, and triggering the AI pipeline happen here.
"""

import os
import uuid
import mimetypes
from flask import request, jsonify, current_app, g, send_file
from werkzeug.utils import secure_filename
import logging
import threading

from models.models import MeetingModel, TranscriptModel, AnalysisModel
from middleware.validation import paginate_params
from utils.file_utils import save_file, delete_file, get_file_duration
from utils.serializer import serialize_meeting, serialize_doc

logger = logging.getLogger(__name__)


# ── Allowed MIME types map ──────────────────────────────────────────────────────
ALLOWED_MIME = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
    "audio/mp4", "audio/m4a", "audio/ogg", "audio/flac",
    "audio/webm", "video/mp4", "video/webm", "video/x-msvideo",
    "video/x-matroska", "video/quicktime",
}


def _allowed_file(filename: str, mime: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"] or mime in ALLOWED_MIME


# ══════════════════════════════════════════════════════════════════════════════
# UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def upload_meeting():
    """
    POST /api/meetings/upload
    Form-data: file (binary), title (str), participants (optional JSON array)
    Returns: { meeting }
    """
    # ── File presence check ────────────────────────────────────────────────────
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file  = request.files["file"]
    title = request.form.get("title", "").strip()

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not title:
        return jsonify({"error": "Meeting title is required"}), 400

    # ── MIME + extension validation ────────────────────────────────────────────
    filename = secure_filename(file.filename)
    mime     = file.mimetype or mimetypes.guess_type(filename)[0] or ""

    if not _allowed_file(filename, mime):
        return jsonify({
            "error": f"Unsupported file type '{mime}'. "
                     f"Allowed: mp3, mp4, wav, m4a, webm, ogg, flac, avi, mkv"
        }), 415

    # ── Size guard (werkzeug enforces MAX_CONTENT_LENGTH too) ─────────────────
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > current_app.config["MAX_CONTENT_LENGTH"]:
        max_mb = current_app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return jsonify({"error": f"File exceeds maximum size of {max_mb} MB"}), 413

    # ── Save file ──────────────────────────────────────────────────────────────
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    try:
        file_path = save_file(file, unique_name, current_app.config)
    except Exception as e:
        logger.error(f"File save failed: {e}")
        return jsonify({"error": "File storage failed"}), 500

    # ── Get duration (best-effort) ─────────────────────────────────────────────
    duration = get_file_duration(file_path)

    # ── Parse optional participants ────────────────────────────────────────────
    import json
    try:
        participants = json.loads(request.form.get("participants", "[]"))
    except (json.JSONDecodeError, TypeError):
        participants = []

    # ── Persist meeting document ───────────────────────────────────────────────
    meeting = MeetingModel.create(
        db=current_app.db,
        user_id=g.current_user_id,
        title=title,
        file_path=file_path,
        file_name=filename,
        file_size=file_size,
        file_type=mime,
        duration_seconds=duration,
        participants=participants,
    )
    meeting_id = str(meeting["_id"])

    # Create placeholder analysis doc so status can be tracked immediately
    AnalysisModel.create(current_app.db, meeting_id)

    # ── Kick off AI pipeline in background thread ──────────────────────────────
    from services.pipeline_service import run_pipeline
    thread = threading.Thread(
        target=run_pipeline,
        args=(current_app._get_current_object(), meeting_id, file_path),
        daemon=True,
    )
    thread.start()
    logger.info(f"Pipeline started for meeting {meeting_id}")

    return jsonify({
        "message": "Meeting uploaded. Analysis started.",
        "meeting": serialize_meeting(meeting),
    }), 201


# ══════════════════════════════════════════════════════════════════════════════
# LIST
# ══════════════════════════════════════════════════════════════════════════════

def list_meetings():
    """
    GET /api/meetings?page=1&limit=10&search=&status=
    Returns: { meetings, total, page, limit, pages }
    """
    page, limit = paginate_params(request)
    search      = request.args.get("search", "").strip() or None
    status      = request.args.get("status", "").strip() or None

    meetings, total = MeetingModel.find_by_user(
        current_app.db, g.current_user_id, page, limit, search, status
    )

    return jsonify({
        "meetings": [serialize_meeting(m) for m in meetings],
        "total":    total,
        "page":     page,
        "limit":    limit,
        "pages":    (total + limit - 1) // limit,
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# GET SINGLE
# ══════════════════════════════════════════════════════════════════════════════

def get_meeting(meeting_id: str):
    """
    GET /api/meetings/<meeting_id>
    Returns full meeting with transcript + analysis if available.
    """
    from middleware.auth_middleware import verify_meeting_ownership
    if not verify_meeting_ownership(meeting_id):
        return jsonify({"error": "Meeting not found or access denied"}), 404

    meeting    = MeetingModel.find_by_id(current_app.db, meeting_id)
    transcript = TranscriptModel.find_by_meeting(current_app.db, meeting_id)
    analysis   = AnalysisModel.find_by_meeting(current_app.db, meeting_id)

    return jsonify({
        "meeting":    serialize_meeting(meeting),
        "transcript": serialize_doc(transcript) if transcript else None,
        "analysis":   serialize_doc(analysis) if analysis else None,
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# STATUS POLL
# ══════════════════════════════════════════════════════════════════════════════

def get_meeting_status(meeting_id: str):
    """
    GET /api/meetings/<meeting_id>/status
    Lightweight poll endpoint for frontend progress tracking.
    """
    from middleware.auth_middleware import verify_meeting_ownership
    if not verify_meeting_ownership(meeting_id):
        return jsonify({"error": "Not found"}), 404

    meeting = MeetingModel.find_by_id(current_app.db, meeting_id)
    return jsonify({
        "status":            meeting["status"],
        "processing_stages": meeting.get("processing_stages", {}),
        "error_message":     meeting.get("error_message"),
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# UPDATE
# ══════════════════════════════════════════════════════════════════════════════

def update_meeting(meeting_id: str):
    """
    PUT /api/meetings/<meeting_id>
    Body: { title, tags, participants }
    """
    from middleware.auth_middleware import verify_meeting_ownership
    if not verify_meeting_ownership(meeting_id):
        return jsonify({"error": "Not found or access denied"}), 404

    data = request.get_json(silent=True) or {}
    from models.models import utcnow

    allowed = ["title", "tags", "participants"]
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    updates["updated_at"] = utcnow()
    from bson import ObjectId
    current_app.db.meetings.update_one({"_id": ObjectId(meeting_id)}, {"$set": updates})
    meeting = MeetingModel.find_by_id(current_app.db, meeting_id)

    return jsonify({"meeting": serialize_meeting(meeting)}), 200


# ══════════════════════════════════════════════════════════════════════════════
# DELETE
# ══════════════════════════════════════════════════════════════════════════════

def delete_meeting(meeting_id: str):
    """
    DELETE /api/meetings/<meeting_id>
    Soft-deletes the meeting. Admins can hard-delete via /api/users/admin/meetings/<id>.
    """
    from middleware.auth_middleware import verify_meeting_ownership
    if not verify_meeting_ownership(meeting_id):
        return jsonify({"error": "Not found or access denied"}), 404

    meeting = MeetingModel.find_by_id(current_app.db, meeting_id)
    MeetingModel.soft_delete(current_app.db, meeting_id)

    # Optionally remove the physical file
    try:
        delete_file(meeting["file_path"], current_app.config)
    except Exception as e:
        logger.warning(f"Could not delete file for meeting {meeting_id}: {e}")

    logger.info(f"Meeting {meeting_id} soft-deleted by user {g.current_user_id}")
    return jsonify({"message": "Meeting deleted"}), 200


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD STATS
# ══════════════════════════════════════════════════════════════════════════════

def get_dashboard_stats():
    """
    GET /api/meetings/stats
    Returns aggregate stats for the current user's dashboard.
    """
    from bson import ObjectId

    uid   = ObjectId(g.current_user_id)
    match = {"$match": {"user_id": uid, "is_deleted": False}}

    # Total meetings + status breakdown
    pipeline_status = [
        match,
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    status_counts = {
        doc["_id"]: doc["count"]
        for doc in current_app.db.meetings.aggregate(pipeline_status)
    }

    # Total duration
    pipeline_dur = [
        match,
        {"$group": {"_id": None, "total_seconds": {"$sum": "$duration_seconds"}}},
    ]
    dur_result    = list(current_app.db.meetings.aggregate(pipeline_dur))
    total_seconds = dur_result[0]["total_seconds"] if dur_result else 0

    # Meetings per week (last 8 weeks)
    from datetime import datetime, timedelta, timezone
    now        = datetime.now(timezone.utc)
    eight_ago  = now - timedelta(weeks=8)
    pipeline_w = [
        {**match, "$match": {"user_id": uid, "is_deleted": False,
                              "created_at": {"$gte": eight_ago}}},
        {"$group": {
            "_id": {
                "year": {"$year": "$created_at"},
                "week": {"$week": "$created_at"},
            },
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id.year": 1, "_id.week": 1}},
    ]
    weekly = list(current_app.db.meetings.aggregate(pipeline_w))

    total = sum(status_counts.values())

    return jsonify({
        "total_meetings":  total,
        "completed":       status_counts.get("completed", 0),
        "pending":         status_counts.get("pending", 0) + status_counts.get("transcribing", 0),
        "failed":          status_counts.get("failed", 0),
        "total_hours":     round(total_seconds / 3600, 1),
        "weekly_meetings": weekly,
    }), 200

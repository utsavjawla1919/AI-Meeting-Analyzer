"""
User Controller — profile updates, preferences, and admin user management.
"""

from flask import request, jsonify, current_app, g
from bson import ObjectId
import logging

from models.models import UserModel, MeetingModel, utcnow
from middleware.validation import validate_email, paginate_params
from utils.serializer import serialize_doc

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# CURRENT USER — profile & preferences
# ══════════════════════════════════════════════════════════════════════════════

def get_profile():
    """GET /api/users/profile"""
    return jsonify({"user": UserModel.safe_dict(g.current_user)}), 200


def update_profile():
    """
    PUT /api/users/profile
    Body: { full_name, avatar_url }
    """
    data = request.get_json(silent=True) or {}
    allowed = ["full_name", "avatar_url"]
    updates = {k: v.strip() if isinstance(v, str) else v
               for k, v in data.items() if k in allowed}

    if not updates:
        return jsonify({"error": "No valid fields provided"}), 400

    if "full_name" in updates and len(updates["full_name"]) < 2:
        return jsonify({"error": "full_name must be at least 2 characters"}), 400

    updates["updated_at"] = utcnow()
    current_app.db.users.update_one(
        {"_id": g.current_user["_id"]},
        {"$set": updates},
    )
    user = UserModel.find_by_id(current_app.db, g.current_user_id)
    return jsonify({"user": UserModel.safe_dict(user)}), 200


def update_preferences():
    """
    PUT /api/users/preferences
    Body: { dark_mode, email_notify, default_language }
    """
    data = request.get_json(silent=True) or {}
    pref_keys = ["dark_mode", "email_notify", "default_language"]
    updates = {"preferences." + k: v for k, v in data.items() if k in pref_keys}

    if not updates:
        return jsonify({"error": "No valid preference fields provided"}), 400

    updates["updated_at"] = utcnow()
    current_app.db.users.update_one(
        {"_id": g.current_user["_id"]},
        {"$set": updates},
    )
    user = UserModel.find_by_id(current_app.db, g.current_user_id)
    return jsonify({"preferences": user.get("preferences", {})}), 200


def delete_account():
    """
    DELETE /api/users/account
    Body: { password } — confirm before deletion.
    Soft-deletes the account and all meetings.
    """
    data     = request.get_json(silent=True) or {}
    password = data.get("password", "")

    if not UserModel.verify_password(password, g.current_user["password"]):
        return jsonify({"error": "Incorrect password"}), 401

    # Deactivate user
    current_app.db.users.update_one(
        {"_id": g.current_user["_id"]},
        {"$set": {"is_active": False, "updated_at": utcnow()}},
    )
    # Soft-delete all their meetings
    current_app.db.meetings.update_many(
        {"user_id": g.current_user["_id"]},
        {"$set": {"is_deleted": True, "updated_at": utcnow()}},
    )
    logger.info(f"Account deactivated: {g.current_user_id}")
    return jsonify({"message": "Account deactivated successfully"}), 200


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — user management
# ══════════════════════════════════════════════════════════════════════════════

def admin_list_users():
    """
    GET /api/users/admin/users?page=1&limit=10&search=
    Admin: list all users with meeting counts.
    """
    page, limit = paginate_params(request)
    search      = request.args.get("search", "").strip()

    query = {}
    if search:
        query["$or"] = [
            {"email":     {"$regex": search, "$options": "i"}},
            {"full_name": {"$regex": search, "$options": "i"}},
        ]

    total   = current_app.db.users.count_documents(query)
    users   = list(
        current_app.db.users.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * limit)
        .limit(limit)
    )

    # Enrich with meeting counts
    result = []
    for u in users:
        count = current_app.db.meetings.count_documents({
            "user_id":    u["_id"],
            "is_deleted": False,
        })
        safe = UserModel.safe_dict(u)
        safe["meeting_count"] = count
        result.append(safe)

    return jsonify({
        "users": result,
        "total": total,
        "page":  page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }), 200


def admin_get_user(user_id: str):
    """GET /api/users/admin/users/<user_id>"""
    user = UserModel.find_by_id(current_app.db, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": UserModel.safe_dict(user)}), 200


def admin_toggle_user(user_id: str):
    """
    PUT /api/users/admin/users/<user_id>/toggle
    Activate or deactivate a user account.
    """
    if user_id == g.current_user_id:
        return jsonify({"error": "Cannot deactivate your own account"}), 400

    user = UserModel.find_by_id(current_app.db, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    new_status = not user.get("is_active", True)
    current_app.db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"is_active": new_status, "updated_at": utcnow()}},
    )
    action = "activated" if new_status else "deactivated"
    logger.info(f"Admin {g.current_user_id} {action} user {user_id}")
    return jsonify({"message": f"User {action}", "is_active": new_status}), 200


def admin_change_role(user_id: str):
    """
    PUT /api/users/admin/users/<user_id>/role
    Body: { role: "user" | "admin" }
    """
    if user_id == g.current_user_id:
        return jsonify({"error": "Cannot change your own role"}), 400

    data = request.get_json(silent=True) or {}
    role = data.get("role", "")

    if role not in ("user", "admin"):
        return jsonify({"error": "role must be 'user' or 'admin'"}), 400

    user = UserModel.find_by_id(current_app.db, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    current_app.db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": role, "updated_at": utcnow()}},
    )
    logger.info(f"Admin {g.current_user_id} changed user {user_id} role to {role}")
    return jsonify({"message": f"Role updated to {role}"}), 200


def admin_delete_meeting(meeting_id: str):
    """
    DELETE /api/users/admin/meetings/<meeting_id>
    Hard delete — removes meeting, transcript, and analysis from DB.
    """
    meeting = MeetingModel.find_by_id(current_app.db, meeting_id)
    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404

    mid = ObjectId(meeting_id)
    current_app.db.meetings.delete_one({"_id": mid})
    current_app.db.transcripts.delete_one({"meeting_id": mid})
    current_app.db.analyses.delete_one({"meeting_id": mid})

    # Remove physical file
    from utils.file_utils import delete_file
    try:
        delete_file(meeting.get("file_path", ""), current_app.config)
    except Exception as e:
        logger.warning(f"Could not remove file: {e}")

    logger.info(f"Admin {g.current_user_id} hard-deleted meeting {meeting_id}")
    return jsonify({"message": "Meeting permanently deleted"}), 200


def admin_platform_stats():
    """
    GET /api/users/admin/stats
    Platform-wide aggregate statistics.
    """
    total_users    = current_app.db.users.count_documents({})
    active_users   = current_app.db.users.count_documents({"is_active": True})
    total_meetings = current_app.db.meetings.count_documents({"is_deleted": False})
    completed      = current_app.db.meetings.count_documents({"status": "completed", "is_deleted": False})
    failed         = current_app.db.meetings.count_documents({"status": "failed", "is_deleted": False})

    dur_result  = list(current_app.db.meetings.aggregate([
        {"$match": {"is_deleted": False}},
        {"$group": {"_id": None, "total": {"$sum": "$duration_seconds"}}},
    ]))
    total_hours = round((dur_result[0]["total"] if dur_result else 0) / 3600, 1)

    return jsonify({
        "total_users":    total_users,
        "active_users":   active_users,
        "total_meetings": total_meetings,
        "completed":      completed,
        "failed":         failed,
        "total_hours":    total_hours,
    }), 200

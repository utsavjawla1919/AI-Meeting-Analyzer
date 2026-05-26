"""
JWT Middleware — decorators for route protection and role enforcement.

Usage:
    @jwt_required_custom          — any authenticated user
    @admin_required               — admin role only
    @get_current_user_id()        — injects user_id into kwargs
"""

from functools import wraps
from flask import jsonify, current_app, g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)


def jwt_required_custom(fn):
    """
    Verify JWT token and attach user document to Flask g.
    Returns 401 if token is missing, expired, or invalid.
    Returns 403 if the user account is deactivated.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()

            # Load user from DB to confirm account is still active
            from models.models import UserModel
            user = UserModel.find_by_id(current_app.db, user_id)
            if not user:
                return jsonify({"error": "User not found"}), 401
            if not user.get("is_active", True):
                return jsonify({"error": "Account deactivated"}), 403

            # Store on Flask g for downstream access
            g.current_user    = user
            g.current_user_id = str(user["_id"])

        except Exception as e:
            logger.warning(f"JWT validation failed: {e}")
            return jsonify({"error": "Invalid or expired token"}), 401

        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    """
    Extends jwt_required_custom — additionally checks for admin role.
    Returns 403 Forbidden if the user is not an admin.
    """
    @wraps(fn)
    @jwt_required_custom
    def wrapper(*args, **kwargs):
        if g.current_user.get("role") != "admin":
            return jsonify({"error": "Admin privileges required"}), 403
        return fn(*args, **kwargs)
    return wrapper


def optional_jwt(fn):
    """
    Soft authentication — attaches user to g if a valid token is present,
    but does NOT reject requests without a token (useful for public routes
    that show extra data when authenticated).
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()
            if user_id:
                from models.models import UserModel
                g.current_user    = UserModel.find_by_id(current_app.db, user_id)
                g.current_user_id = user_id
            else:
                g.current_user    = None
                g.current_user_id = None
        except Exception:
            g.current_user    = None
            g.current_user_id = None
        return fn(*args, **kwargs)
    return wrapper


def verify_meeting_ownership(meeting_id: str) -> bool:
    """
    Helper — confirms the current user owns the meeting,
    or is an admin. Returns True if authorized.
    """
    from models.models import MeetingModel
    meeting = MeetingModel.find_by_id(current_app.db, meeting_id)
    if not meeting:
        return False
    if g.current_user.get("role") == "admin":
        return True
    return str(meeting["user_id"]) == g.current_user_id

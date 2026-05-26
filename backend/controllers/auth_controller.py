"""
Auth Controller — handles registration, login, token refresh, and logout.
All business logic lives here; routes just call these functions.
"""

from flask import request, jsonify, current_app, g
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    get_jwt,
)
from datetime import timezone
import logging

from models.models import UserModel
from middleware.validation import validate_email, validate_password

logger = logging.getLogger(__name__)

# In-memory token blocklist (production: use Redis)
TOKEN_BLOCKLIST: set = set()


def register():
    """
    POST /api/auth/register
    Body: { email, password, full_name }
    Returns: { user, access_token, refresh_token }
    """
    data = request.get_json(silent=True) or {}

    # ── Validate input ─────────────────────────────────────────────────────────
    email     = data.get("email", "").strip().lower()
    password  = data.get("password", "")
    full_name = data.get("full_name", "").strip()

    if not all([email, password, full_name]):
        return jsonify({"error": "email, password, and full_name are required"}), 400

    if not validate_email(email):
        return jsonify({"error": "Invalid email address"}), 400

    valid, msg = validate_password(password)
    if not valid:
        return jsonify({"error": msg}), 400

    if len(full_name) < 2:
        return jsonify({"error": "full_name must be at least 2 characters"}), 400

    # ── Check uniqueness ───────────────────────────────────────────────────────
    if UserModel.find_by_email(current_app.db, email):
        return jsonify({"error": "An account with this email already exists"}), 409

    # ── Create user ────────────────────────────────────────────────────────────
    try:
        user         = UserModel.create(current_app.db, email, password, full_name)
        user_id      = str(user["_id"])
        access_token  = create_access_token(identity=user_id)
        refresh_token = create_refresh_token(identity=user_id)

        logger.info(f"New user registered: {email}")
        return jsonify({
            "message":       "Account created successfully",
            "user":          UserModel.safe_dict(user),
            "access_token":  access_token,
            "refresh_token": refresh_token,
        }), 201

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({"error": "Registration failed. Please try again."}), 500


def login():
    """
    POST /api/auth/login
    Body: { email, password }
    Returns: { user, access_token, refresh_token }
    """
    data     = request.get_json(silent=True) or {}
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    # ── Look up user ───────────────────────────────────────────────────────────
    user = UserModel.find_by_email(current_app.db, email)
    if not user or not UserModel.verify_password(password, user["password"]):
        return jsonify({"error": "Invalid email or password"}), 401

    if not user.get("is_active", True):
        return jsonify({"error": "Account is deactivated. Contact support."}), 403

    # ── Issue tokens ───────────────────────────────────────────────────────────
    user_id       = str(user["_id"])
    access_token  = create_access_token(identity=user_id)
    refresh_token = create_refresh_token(identity=user_id)

    UserModel.update_last_login(current_app.db, user_id)
    logger.info(f"User logged in: {email}")

    return jsonify({
        "message":       "Login successful",
        "user":          UserModel.safe_dict(user),
        "access_token":  access_token,
        "refresh_token": refresh_token,
    }), 200


def refresh():
    """
    POST /api/auth/refresh
    Header: Authorization: Bearer <refresh_token>
    Returns: { access_token }
    """
    try:
        user_id      = get_jwt_identity()
        access_token = create_access_token(identity=user_id)
        return jsonify({"access_token": access_token}), 200
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return jsonify({"error": "Could not refresh token"}), 401


def logout():
    """
    POST /api/auth/logout
    Adds the current JWT's jti to the blocklist.
    """
    try:
        jti = get_jwt()["jti"]
        TOKEN_BLOCKLIST.add(jti)
        logger.info(f"User {g.current_user_id} logged out")
        return jsonify({"message": "Logged out successfully"}), 200
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({"error": "Logout failed"}), 500


def get_me():
    """
    GET /api/auth/me
    Returns the current authenticated user's profile.
    """
    return jsonify({"user": UserModel.safe_dict(g.current_user)}), 200


def change_password():
    """
    PUT /api/auth/password
    Body: { current_password, new_password }
    """
    data             = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "")
    new_password     = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"error": "current_password and new_password are required"}), 400

    # Verify existing password
    if not UserModel.verify_password(current_password, g.current_user["password"]):
        return jsonify({"error": "Current password is incorrect"}), 401

    valid, msg = validate_password(new_password)
    if not valid:
        return jsonify({"error": msg}), 400

    # Update
    import bcrypt
    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
    from models.models import utcnow
    current_app.db.users.update_one(
        {"_id": g.current_user["_id"]},
        {"$set": {"password": hashed, "updated_at": utcnow()}},
    )
    return jsonify({"message": "Password updated successfully"}), 200

"""Auth routes — /api/auth/*"""

from flask import Blueprint
from flask_jwt_extended import jwt_required

from controllers.auth_controller import (
    register, login, refresh, logout, get_me, change_password,
)
from middleware.auth_middleware import jwt_required_custom

auth_bp = Blueprint("auth", __name__)

# Public routes
auth_bp.post("/register")(register)
auth_bp.post("/login")(login)

# Refresh token route (requires valid refresh token)
auth_bp.post("/refresh")(jwt_required(refresh=True)(refresh))

# Protected routes
auth_bp.get("/me")(jwt_required_custom(get_me))
auth_bp.post("/logout")(jwt_required_custom(logout))
auth_bp.put("/password")(jwt_required_custom(change_password))

"""User routes — /api/users/*"""

from flask import Blueprint
from middleware.auth_middleware import jwt_required_custom, admin_required
from controllers.user_controller import (
    get_profile, update_profile, update_preferences, delete_account,
    admin_list_users, admin_get_user, admin_toggle_user,
    admin_change_role, admin_delete_meeting, admin_platform_stats,
)

users_bp = Blueprint("users", __name__)

# Current-user routes
users_bp.get("/profile")(jwt_required_custom(get_profile))
users_bp.put("/profile")(jwt_required_custom(update_profile))
users_bp.put("/preferences")(jwt_required_custom(update_preferences))
users_bp.delete("/account")(jwt_required_custom(delete_account))

# Admin routes
users_bp.get("/admin/stats")(admin_required(admin_platform_stats))
users_bp.get("/admin/users")(admin_required(admin_list_users))
users_bp.get("/admin/users/<user_id>")(admin_required(admin_get_user))
users_bp.put("/admin/users/<user_id>/toggle")(admin_required(admin_toggle_user))
users_bp.put("/admin/users/<user_id>/role")(admin_required(admin_change_role))
users_bp.delete("/admin/meetings/<meeting_id>")(admin_required(admin_delete_meeting))

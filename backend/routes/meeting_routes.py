"""Meeting routes — /api/meetings/*"""

from flask import Blueprint
from middleware.auth_middleware import jwt_required_custom
from controllers.meeting_controller import (
    upload_meeting, list_meetings, get_meeting,
    get_meeting_status, update_meeting, delete_meeting,
    get_dashboard_stats,
)

meetings_bp = Blueprint("meetings", __name__)

# All meeting routes require authentication
meetings_bp.get("/stats")(jwt_required_custom(get_dashboard_stats))
meetings_bp.post("/upload")(jwt_required_custom(upload_meeting))
meetings_bp.get("/")(jwt_required_custom(list_meetings))
meetings_bp.get("/<meeting_id>")(jwt_required_custom(get_meeting))
meetings_bp.get("/<meeting_id>/status")(jwt_required_custom(get_meeting_status))
meetings_bp.put("/<meeting_id>")(jwt_required_custom(update_meeting))
meetings_bp.delete("/<meeting_id>")(jwt_required_custom(delete_meeting))

"""Analysis routes — /api/analysis/*"""

from flask import Blueprint
from middleware.auth_middleware import jwt_required_custom
from controllers.analysis_controller import (
    get_analysis, get_transcript, get_sentiment,
    get_action_items, get_keywords, retry_analysis, search_meetings,
)

analysis_bp = Blueprint("analysis", __name__)

analysis_bp.get("/search")(jwt_required_custom(search_meetings))
analysis_bp.get("/<meeting_id>")(jwt_required_custom(get_analysis))
analysis_bp.get("/<meeting_id>/transcript")(jwt_required_custom(get_transcript))
analysis_bp.get("/<meeting_id>/sentiment")(jwt_required_custom(get_sentiment))
analysis_bp.get("/<meeting_id>/actions")(jwt_required_custom(get_action_items))
analysis_bp.get("/<meeting_id>/keywords")(jwt_required_custom(get_keywords))
analysis_bp.post("/<meeting_id>/retry")(jwt_required_custom(retry_analysis))

"""Export routes — /api/export/*"""

from flask import Blueprint
from middleware.auth_middleware import jwt_required_custom
from controllers.export_controller import export_meeting_pdf, export_transcript_pdf

export_bp = Blueprint("export", __name__)

export_bp.get("/<meeting_id>/pdf")(jwt_required_custom(export_meeting_pdf))
export_bp.get("/<meeting_id>/transcript")(jwt_required_custom(export_transcript_pdf))

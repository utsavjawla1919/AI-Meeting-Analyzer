"""
Serializer — converts MongoDB documents (with ObjectId, datetime)
into JSON-serializable Python dicts for API responses.
"""

from datetime import datetime
from bson import ObjectId
from typing import Any


def _convert(value: Any) -> Any:
    """Recursively convert MongoDB types to JSON-safe primitives."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _convert(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert(item) for item in value]
    if isinstance(value, bytes):
        return None   # strip binary fields (e.g. hashed password)
    return value


def serialize_doc(doc: dict) -> dict:
    """Serialize a single MongoDB document."""
    if not doc:
        return {}
    return _convert(dict(doc))


def serialize_meeting(meeting: dict) -> dict:
    """
    Serialize a meeting document with human-friendly computed fields.
    Strips the internal file_path for security.
    """
    if not meeting:
        return {}
    doc = _convert(dict(meeting))
    doc.pop("file_path", None)   # never expose storage path to client
    return doc


def serialize_list(docs: list) -> list:
    """Serialize a list of MongoDB documents."""
    return [serialize_doc(d) for d in docs]


def paginated_response(items: list, total: int, page: int, limit: int) -> dict:
    """Standard shape for paginated list responses."""
    return {
        "items": items,
        "total": total,
        "page":  page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit > 0 else 1,
    }

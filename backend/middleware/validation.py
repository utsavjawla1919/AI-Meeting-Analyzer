"""
Validation helpers — sanitize and validate incoming request data.
"""

import re
from flask import jsonify
from functools import wraps


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))


def validate_password(password: str) -> tuple[bool, str]:
    """Returns (is_valid, error_message)."""
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one digit"
    return True, ""


def require_json(fn):
    """Decorator — return 400 if Content-Type is not application/json."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from flask import request
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        return fn(*args, **kwargs)
    return wrapper


def paginate_params(request) -> tuple[int, int]:
    """Extract and clamp page/limit from query string."""
    from flask import current_app
    try:
        page  = max(1, int(request.args.get("page", 1)))
        limit = min(
            int(request.args.get("limit", current_app.config["DEFAULT_PAGE_SIZE"])),
            current_app.config["MAX_PAGE_SIZE"],
        )
    except (ValueError, TypeError):
        page, limit = 1, 10
    return page, limit

"""
token_blocklist.py — Production-safe JWT revocation using MongoDB TTL index.
Tokens added here are rejected by the JWT middleware on every request.
The TTL index auto-purges expired entries so the collection stays lean.
"""

from datetime import datetime, timezone
from bson import ObjectId
from models.models import new_id, utcnow


class TokenBlocklist:
    COLLECTION = "token_blocklist"

    @staticmethod
    def add(db, jti: str, expires_at: datetime, user_id: str = None):
        """
        Blocklist a JWT by its jti (JWT ID claim).
        expires_at: the token's own expiry — MongoDB TTL index removes
                    the document automatically after this timestamp.
        """
        doc = {
            "_id":        new_id(),
            "jti":        jti,
            "user_id":    ObjectId(user_id) if user_id else None,
            "expires_at": expires_at,        # TTL field — must be a datetime
            "created_at": utcnow(),
        }
        db[TokenBlocklist.COLLECTION].insert_one(doc)

    @staticmethod
    def is_revoked(db, jti: str) -> bool:
        """Return True if the jti is in the blocklist (token has been logged out)."""
        return db[TokenBlocklist.COLLECTION].find_one({"jti": jti}) is not None

    @staticmethod
    def revoke_all_for_user(db, user_id: str):
        """
        Revoke all active tokens for a user (e.g. on password change or account lock).
        In practice this marks a 'revoked_before' timestamp on the user document;
        the JWT middleware then checks issued-at (iat) against this timestamp.
        """
        from models.models import utcnow
        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"tokens_revoked_before": utcnow()}},
        )

    @staticmethod
    def init_ttl_index(db):
        """
        Create a TTL index on expires_at so MongoDB auto-deletes
        blocklisted tokens once they've expired.
        Safe to call multiple times (idempotent).
        """
        db[TokenBlocklist.COLLECTION].create_index(
            "expires_at",
            expireAfterSeconds=0,   # delete at the expires_at time itself
            name="blocklist_ttl",
        )
        db[TokenBlocklist.COLLECTION].create_index(
            "jti",
            unique=True,
            name="blocklist_jti_unique",
        )

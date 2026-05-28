from datetime import datetime, timezone
from bson import ObjectId
import bcrypt
from flask import current_app


# ── Helpers ────────────────────────────────────────────────────────────────────

def utcnow():
    return datetime.now(timezone.utc)


def new_id():
    return ObjectId()


# ══════════════════════════════════════════════════════════════════════════════
# USERS COLLECTION
# ══════════════════════════════════════════════════════════════════════════════

class UserModel:
    COLLECTION = "users"

    ROLES = ("user", "admin")

    @staticmethod
    def create(db, email: str, password: str, full_name: str, role: str = "user") -> dict:

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        doc = {
            "_id": new_id(),
            "email": email.lower().strip(),
            "password": hashed,
            "full_name": full_name.strip(),
            "role": role,
            "avatar_url": None,
            "preferences": {
                "dark_mode": False,
                "email_notify": True,
                "default_language": "en",
            },
            "is_active": True,
            "last_login": None,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }

        db[UserModel.COLLECTION].insert_one(doc)

        return UserModel.safe_dict(doc)

    @staticmethod
    def verify_password(plain: str, hashed: bytes) -> bool:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed)

    @staticmethod
    def find_by_email(db, email: str):
        return db[UserModel.COLLECTION].find_one(
            {"email": email.lower().strip()}
        )

    @staticmethod
    def find_by_id(db, user_id):
        return db[UserModel.COLLECTION].find_one(
            {"_id": ObjectId(user_id)}
        )

    @staticmethod
    def safe_dict(user: dict) -> dict:

        u = {k: v for k, v in user.items() if k != "password"}

        # ObjectId → string
        if "_id" in u:
            u["_id"] = str(u["_id"])

        # Datetime → iso string
        if u.get("created_at"):
            u["created_at"] = u["created_at"].isoformat()

        if u.get("updated_at"):
            u["updated_at"] = u["updated_at"].isoformat()

        if u.get("last_login"):
            u["last_login"] = u["last_login"].isoformat()

        return u

    @staticmethod
    def update_last_login(db, user_id):

        db[UserModel.COLLECTION].update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "last_login": utcnow(),
                    "updated_at": utcnow()
                }
            },
        )
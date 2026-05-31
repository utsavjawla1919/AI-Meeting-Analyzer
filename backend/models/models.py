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

        if "_id" in u:
            u["_id"] = str(u["_id"])

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


# ══════════════════════════════════════════════════════════════════════════════
# MEETINGS COLLECTION
# ══════════════════════════════════════════════════════════════════════════════

class MeetingModel:
    COLLECTION = "meetings"

    @staticmethod
    def create(db, user_id, title: str, file_path: str, file_name: str,
               file_size: int = 0, file_type: str = None,
               duration_seconds: int = None, participants: list = None) -> dict:
        doc = {
            "_id": new_id(),
            "user_id": ObjectId(user_id),
            "title": title.strip(),
            "file_path": file_path,
            "file_name": file_name,
            "file_size": file_size,
            "file_type": file_type,
            "status": "pending",
            "error_message": None,
            "stages": {
                "transcription": "pending",
                "nlp":           "pending",
                "summarization": "pending",
                "sentiment":     "pending",
            },
            "duration_seconds": duration_seconds,
            "participants": participants or [],
            "is_deleted": False,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        db[MeetingModel.COLLECTION].insert_one(doc)
        doc["_id"] = str(doc["_id"])
        doc["user_id"] = str(doc["user_id"])
        return doc

    @staticmethod
    def find_by_id(db, meeting_id) -> dict:
        return db[MeetingModel.COLLECTION].find_one({
            "_id": ObjectId(meeting_id),
            "is_deleted": False,
        })

    @staticmethod
    def find_by_user(db, user_id, page: int = 1, limit: int = 10,
                     search: str = None, status: str = None):
        query = {"user_id": ObjectId(user_id), "is_deleted": False}
        if search:
            query["title"] = {"$regex": search, "$options": "i"}
        if status:
            query["status"] = status
        skip = (page - 1) * limit
        total = db[MeetingModel.COLLECTION].count_documents(query)
        cursor = (db[MeetingModel.COLLECTION]
                  .find(query)
                  .sort("created_at", -1)
                  .skip(skip)
                  .limit(limit))
        return list(cursor), total

    @staticmethod
    def set_status(db, meeting_id, status: str, error_message: str = None):
        update = {"status": status, "updated_at": utcnow()}
        if error_message:
            update["error_message"] = error_message
        db[MeetingModel.COLLECTION].update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": update},
        )

    @staticmethod
    def set_stage(db, meeting_id, stage: str, status: str):
        db[MeetingModel.COLLECTION].update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": {f"stages.{stage}": status, "updated_at": utcnow()}},
        )

    @staticmethod
    def soft_delete(db, meeting_id):
        db[MeetingModel.COLLECTION].update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": {"is_deleted": True, "updated_at": utcnow()}},
        )


# ══════════════════════════════════════════════════════════════════════════════
# TRANSCRIPTS COLLECTION
# ══════════════════════════════════════════════════════════════════════════════

class TranscriptModel:
    COLLECTION = "transcripts"

    @staticmethod
    def create(db, meeting_id, full_text: str, segments: list,
               language: str = "en") -> dict:
        doc = {
            "_id": new_id(),
            "meeting_id": ObjectId(meeting_id),
            "full_text": full_text,
            "segments": segments,
            "language": language,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        db[TranscriptModel.COLLECTION].insert_one(doc)
        return doc

    @staticmethod
    def find_by_meeting(db, meeting_id) -> dict:
        return db[TranscriptModel.COLLECTION].find_one(
            {"meeting_id": ObjectId(meeting_id)}
        )


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS COLLECTION
# ══════════════════════════════════════════════════════════════════════════════

class AnalysisModel:
    COLLECTION = "analysis"

    @staticmethod
    def create(db, meeting_id) -> dict:
        doc = {
            "_id": new_id(),
            "meeting_id": ObjectId(meeting_id),
            "keywords": [],
            "entities": [],
            "topics": [],
            "key_points": [],
            "noun_chunks": [],
            "summary": None,
            "ai_title": None,
            "action_items": [],
            "decisions": [],
            "recommendations": [],
            "sentiment_overall": {},
            "sentiment_by_speaker": {},
            "sentiment_timeline": [],
            "meeting_score": None,
            "health": {},
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        db[AnalysisModel.COLLECTION].insert_one(doc)
        return doc

    @staticmethod
    def find_by_meeting(db, meeting_id) -> dict:
        return db[AnalysisModel.COLLECTION].find_one(
            {"meeting_id": ObjectId(meeting_id)}
        )

    @staticmethod
    def update(db, meeting_id, fields: dict):
        fields["updated_at"] = utcnow()
        db[AnalysisModel.COLLECTION].update_one(
            {"meeting_id": ObjectId(meeting_id)},
            {"$set": fields},
        )
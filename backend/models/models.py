"""
MongoDB Models — schema definitions, validators, and index setup.
Uses PyMongo directly (no ODM) for full control and performance.
Call `init_indexes(db)` once at startup to ensure indexes exist.
"""

from datetime import datetime, timezone
from bson import ObjectId
import bcrypt


# ── Helpers ────────────────────────────────────────────────────────────────────

def utcnow():
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def new_id():
    """Generate a new MongoDB ObjectId."""
    return ObjectId()


# ══════════════════════════════════════════════════════════════════════════════
# USERS COLLECTION
# ══════════════════════════════════════════════════════════════════════════════

class UserModel:
    COLLECTION = "users"

    ROLES = ("user", "admin")

    @staticmethod
    def create(db, email: str, password: str, full_name: str, role: str = "user") -> dict:
        """Hash password and insert a new user document."""
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        doc = {
            "_id":          new_id(),
            "email":        email.lower().strip(),
            "password":     hashed,               # bytes — stored as Binary in Mongo
            "full_name":    full_name.strip(),
            "role":         role,
            "avatar_url":   None,
            "preferences": {
                "dark_mode":       False,
                "email_notify":    True,
                "default_language": "en",
            },
            "is_active":    True,
            "last_login":   None,
            "created_at":   utcnow(),
            "updated_at":   utcnow(),
        }
        db[UserModel.COLLECTION].insert_one(doc)
        return doc

    @staticmethod
    def verify_password(plain: str, hashed: bytes) -> bool:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed)

    @staticmethod
    def find_by_email(db, email: str):
        return db[UserModel.COLLECTION].find_one({"email": email.lower().strip()})

    @staticmethod
    def find_by_id(db, user_id):
        return db[UserModel.COLLECTION].find_one({"_id": ObjectId(user_id)})

    @staticmethod
def safe_dict(user: dict) -> dict:
    """Convert Mongo user document into JSON-safe dict."""

    u = {k: v for k, v in user.items() if k != "password"}

    # Convert ObjectId
    u["_id"] = str(u["_id"])

    # Convert datetime objects
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
            {"$set": {"last_login": utcnow(), "updated_at": utcnow()}},
        )


# ══════════════════════════════════════════════════════════════════════════════
# MEETINGS COLLECTION
# ══════════════════════════════════════════════════════════════════════════════

class MeetingModel:
    COLLECTION = "meetings"

    # Processing pipeline states
    STATUS = ("pending", "uploading", "transcribing", "analyzing", "completed", "failed")

    @staticmethod
    def create(db, user_id: str, title: str, file_path: str,
               file_name: str, file_size: int, file_type: str,
               duration_seconds: int = 0, participants: list = None) -> dict:
        doc = {
            "_id":               new_id(),
            "user_id":           ObjectId(user_id),
            "title":             title,
            "ai_title":          None,           # set after analysis
            "file_path":         file_path,      # local path or S3 key
            "file_name":         file_name,
            "file_size":         file_size,      # bytes
            "file_type":         file_type,      # mime type
            "duration_seconds":  duration_seconds,
            "participants":      participants or [],
            "language":           "english",           # detected by Whisper
            "status":            "pending",
            "error_message":     None,
            "processing_stages": {               # granular progress tracking
                "upload":       "pending",
                "transcription": "pending",
                "nlp":          "pending",
                "summarization": "pending",
                "sentiment":    "pending",
            },
            "tags":        [],
            "is_deleted":  False,
            "created_at":  utcnow(),
            "updated_at":  utcnow(),
        }
        db[MeetingModel.COLLECTION].insert_one(doc)
        return doc

    @staticmethod
    def set_status(db, meeting_id, status: str, error: str = None):
        update = {"$set": {"status": status, "updated_at": utcnow()}}
        if error:
            update["$set"]["error_message"] = error
        db[MeetingModel.COLLECTION].update_one({"_id": ObjectId(meeting_id)}, update)

    @staticmethod
    def set_stage(db, meeting_id, stage: str, status: str):
        """Update a single processing stage (e.g. transcription → completed)."""
        db[MeetingModel.COLLECTION].update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": {f"processing_stages.{stage}": status, "updated_at": utcnow()}},
        )

    @staticmethod
    def find_by_user(db, user_id: str, page: int = 1, limit: int = 10,
                     search: str = None, status: str = None) -> tuple:
        query = {"user_id": ObjectId(user_id), "is_deleted": False}
        if search:
            query["$or"] = [
                {"title":    {"$regex": search, "$options": "i"}},
                {"ai_title": {"$regex": search, "$options": "i"}},
                {"tags":     {"$in": [search]}},
            ]
        if status:
            query["status"] = status

        total  = db[MeetingModel.COLLECTION].count_documents(query)
        cursor = (
            db[MeetingModel.COLLECTION]
            .find(query)
            .sort("created_at", -1)
            .skip((page - 1) * limit)
            .limit(limit)
        )
        return list(cursor), total

    @staticmethod
    def find_by_id(db, meeting_id, user_id: str = None):
        query = {"_id": ObjectId(meeting_id), "is_deleted": False}
        if user_id:
            query["user_id"] = ObjectId(user_id)
        return db[MeetingModel.COLLECTION].find_one(query)

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
    def create(db, meeting_id: str, full_text: str,
               segments: list, language: str = "en") -> dict:
        """
        segments = [
          {"speaker": "Speaker 1", "start": 0.0, "end": 4.2, "text": "Hello everyone."},
          ...
        ]
        """
        doc = {
            "_id":        new_id(),
            "meeting_id": ObjectId(meeting_id),
            "full_text":  full_text,
            "segments":   segments,
            "language":   language,
            "word_count": len(full_text.split()),
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        db[TranscriptModel.COLLECTION].insert_one(doc)
        return doc

    @staticmethod
    def find_by_meeting(db, meeting_id):
        return db[TranscriptModel.COLLECTION].find_one({"meeting_id": ObjectId(meeting_id)})

    @staticmethod
    def update_segments(db, transcript_id, segments: list):
        db[TranscriptModel.COLLECTION].update_one(
            {"_id": ObjectId(transcript_id)},
            {"$set": {"segments": segments, "updated_at": utcnow()}},
        )


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSES COLLECTION
# ══════════════════════════════════════════════════════════════════════════════

class AnalysisModel:
    COLLECTION = "analyses"

    @staticmethod
    def create(db, meeting_id: str) -> dict:
        """Create a blank analysis document; fields filled as pipeline runs."""
        doc = {
            "_id":          new_id(),
            "meeting_id":   ObjectId(meeting_id),
            # Summarization
            "summary":      None,
            "ai_title":     None,
            # Extraction
            "action_items": [],   # [{text, assignee, due_date, priority}]
            "decisions":    [],   # [{text, context}]
            "key_points":   [],   # [str]
            # NLP
            "keywords":     [],   # [{word, score, frequency}]
            "topics":       [],   # [{label, confidence, keywords}]
            "entities":     [],   # [{text, label, type}]  (PERSON, ORG, DATE…)
            # Sentiment
            "sentiment_overall": {
                "label":      None,   # positive | negative | neutral
                "score":      None,   # 0.0–1.0
                "positive":   0.0,
                "negative":   0.0,
                "neutral":    0.0,
            },
            "sentiment_by_speaker": {},    # {speaker_id: {label, score}}
            "sentiment_timeline":   [],    # [{segment_index, label, score}]
            # Recommendations
            "recommendations": [],    # [str]
            "meeting_score":   None,  # 0-100 productivity score
            "created_at":      utcnow(),
            "updated_at":      utcnow(),
        }
        db[AnalysisModel.COLLECTION].insert_one(doc)
        return doc

    @staticmethod
    def find_by_meeting(db, meeting_id):
        return db[AnalysisModel.COLLECTION].find_one({"meeting_id": ObjectId(meeting_id)})

    @staticmethod
    def update(db, meeting_id: str, updates: dict):
        updates["updated_at"] = utcnow()
        db[AnalysisModel.COLLECTION].update_one(
            {"meeting_id": ObjectId(meeting_id)},
            {"$set": updates},
        )

# ══════════════════════════════════════════════════════════════════════════════
# INDEX INITIALIZATION
# ══════════════════════════════════════════════════════════════════════════════

def init_indexes(db):
    """Create all MongoDB indexes. Safe to call on every startup (idempotent)."""

    # users
    db.users.create_index("email", unique=True)
    db.users.create_index("role")

    # meetings
    db.meetings.create_index("user_id")
    db.meetings.create_index("status")
    db.meetings.create_index([("created_at", -1)])
    db.meetings.create_index([("title", "text"), ("ai_title", "text")])

    # transcripts
    db.transcripts.create_index("meeting_id", unique=True)

    # analyses
    db.analyses.create_index("meeting_id", unique=True)

    print("✅ MongoDB indexes initialized")

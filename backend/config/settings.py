"""
Configuration settings loaded from environment variables.
Supports Development, Testing, and Production modes.
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration shared across all environments."""

    # ── Flask core ─────────────────────────────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    FLASK_ENV  = os.getenv("FLASK_ENV", "development")
    DEBUG      = False

    # ── JWT ────────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY            = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(hours=int(os.getenv("JWT_ACCESS_HOURS", 1)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", 30)))
    JWT_ALGORITHM             = "HS256"

    # ── MongoDB ────────────────────────────────────────────────────────────────
    MONGO_URI     = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "ai_meeting_analyzer")

    # ── File upload ────────────────────────────────────────────────────────────
    UPLOAD_FOLDER       = os.getenv("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH  = int(os.getenv("MAX_UPLOAD_MB", 500)) * 1024 * 1024  # bytes
    ALLOWED_EXTENSIONS  = {"mp3", "mp4", "wav", "m4a", "webm", "ogg", "flac", "avi", "mkv"}

    # ── CORS ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

    # ── AI services ────────────────────────────────────────────────────────────
    OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY", "")
    WHISPER_MODEL       = os.getenv("WHISPER_MODEL", "base")          # tiny|base|small|medium|large
    SUMMARIZER_MODEL    = os.getenv("SUMMARIZER_MODEL", "facebook/bart-large-cnn")
    SENTIMENT_MODEL     = os.getenv("SENTIMENT_MODEL", "distilbert-base-uncased-finetuned-sst-2-english")

    # ── AWS S3 (optional — falls back to local storage) ────────────────────────
    USE_S3             = os.getenv("USE_S3", "false").lower() == "true"
    AWS_ACCESS_KEY_ID  = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_KEY     = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_BUCKET_NAME    = os.getenv("AWS_BUCKET_NAME", "")
    AWS_REGION         = os.getenv("AWS_REGION", "us-east-1")

    # ── Pagination ─────────────────────────────────────────────────────────────
    DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", 10))
    MAX_PAGE_SIZE     = int(os.getenv("MAX_PAGE_SIZE", 50))

    # ── Rate limiting ──────────────────────────────────────────────────────────
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "200 per day;50 per hour")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(minutes=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)


class TestingConfig(Config):
    TESTING        = True
    MONGO_DB_NAME  = "ai_meeting_analyzer_test"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)


# Map string names → config classes
config_map = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
}

# Active config resolved from ENV
Config = config_map.get(os.getenv("FLASK_ENV", "development"), DevelopmentConfig)

"""
AI Meeting Analyzer — Flask Application Entry Point
Initializes app, registers blueprints, configures extensions.
"""

from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from pymongo import MongoClient
from config.settings import Config
import logging
import os

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log"),
    ],
)
logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    """Application factory — creates and configures the Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Extensions ─────────────────────────────────────────────────────────────
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    jwt = JWTManager(app)

    # ── MongoDB connection ──────────────────────────────────────────────────────
    client = MongoClient(app.config["MONGO_URI"])
    app.db = client[app.config["MONGO_DB_NAME"]]
    logger.info(f"Connected to MongoDB: {app.config['MONGO_DB_NAME']}")

    # ── JWT error handlers ──────────────────────────────────────────────────────
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token has expired", "code": "TOKEN_EXPIRED"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({"error": "Invalid token", "code": "TOKEN_INVALID"}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({"error": "Authorization token required", "code": "TOKEN_MISSING"}), 401

    # ── Register blueprints ─────────────────────────────────────────────────────
    from routes.auth_routes import auth_bp
    from routes.meeting_routes import meetings_bp
    from routes.analysis_routes import analysis_bp
    from routes.user_routes import users_bp
    from routes.export_routes import export_bp

    app.register_blueprint(auth_bp,     url_prefix="/api/auth")
    app.register_blueprint(meetings_bp, url_prefix="/api/meetings")
    app.register_blueprint(analysis_bp, url_prefix="/api/analysis")
    app.register_blueprint(users_bp,    url_prefix="/api/users")
    app.register_blueprint(export_bp,   url_prefix="/api/export")

    # ── Health check ────────────────────────────────────────────────────────────
    @app.route("/api/health")
    def health():
        try:
            app.db.command("ping")
            db_status = "connected"
        except Exception:
            db_status = "disconnected"
        return jsonify({"status": "ok", "database": db_status, "version": "1.0.0"}), 200

    # ── Global error handlers ───────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Internal server error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    logger.info("Flask app initialized successfully")
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_ENV") == "development",
    )

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the application
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base application configuration."""

    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads and Storage
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "app" / "static" / "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))  # 5 MB
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}

    # Subdirectories for uploads
    REFERENCE_UPLOAD_DIR = os.path.join(UPLOAD_FOLDER, "references")
    SCAN_UPLOAD_DIR = os.path.join(UPLOAD_FOLDER, "scans")
    EMBEDDING_DIR = os.path.join(UPLOAD_FOLDER, "embeddings")

    # Rate Limiting & Security
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "True").lower() in ("true", "1")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_STRATEGY = "fixed-window"

    # AI Feature Matching & Thresholds
    MODEL_NAME = os.getenv("MODEL_NAME", "MobileNetV2")
    SIMILARITY_THRESHOLD_HIGH = float(os.getenv("SIMILARITY_THRESHOLD_HIGH", 0.82))
    SIMILARITY_THRESHOLD_MODERATE = float(os.getenv("SIMILARITY_THRESHOLD_MODERATE", 0.65))
    SIMILARITY_THRESHOLD_MINIMUM = float(os.getenv("SIMILARITY_THRESHOLD_MINIMUM", 0.40))

    @classmethod
    def init_app(cls, app):
        pass


class DevelopmentConfig(Config):
    """Development environment configuration."""

    DEBUG = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'productguard.db'}"
    )


class TestingConfig(Config):
    """Testing configuration for automated tests."""

    DEBUG = False
    TESTING = True
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    UPLOAD_FOLDER = str(BASE_DIR / "tests" / "test_uploads")
    REFERENCE_UPLOAD_DIR = os.path.join(UPLOAD_FOLDER, "references")
    SCAN_UPLOAD_DIR = os.path.join(UPLOAD_FOLDER, "scans")
    EMBEDDING_DIR = os.path.join(UPLOAD_FOLDER, "embeddings")


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    TESTING = False
    # In production, require secure secrets and PostgreSQL database
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        assert os.getenv("SECRET_KEY"), "SECRET_KEY environment variable must be set in production!"
        assert os.getenv("DATABASE_URL"), "DATABASE_URL environment variable must be set in production!"


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

"""
InfoPulse — Application Configuration
======================================
All settings read from environment variables / .env file.
Uses pydantic-settings for validation and auto-loading.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    ENVIRONMENT: str = "development"
    APP_VERSION: str = "1.0.0"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:4173"]
    TRUSTED_HOSTS: list[str] = ["localhost", "127.0.0.1", "testserver"]
    ADMIN_EMAILS: list[str] = []
    METRICS_TOKEN: str = ""
    DATA_RETENTION_DAYS: int = 365
    SLOW_QUERY_MS: int = 500

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://infopulse:infopulse@localhost:5432/infopulse"
    AUTO_CREATE_TABLES: bool = False

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- JWT ---
    JWT_SECRET_KEY: str = "change-me-to-a-random-string-at-least-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- LLM ---
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"

    # --- Task scheduler and delivery ---
    TASK_SCHEDULER_ENABLED: bool = True
    TASK_SCHEDULER_POLL_SECONDS: int = 30
    TASK_WORKER_CONCURRENCY: int = 4
    RUN_BACKGROUND_WORKERS_IN_API: bool = True
    KNOWLEDGE_WORKER_POLL_SECONDS: int = 2
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    WEBHOOK_TIMEOUT_SECONDS: int = 10

    # --- Private knowledge storage ---
    KNOWLEDGE_STORAGE_BACKEND: str = "local"
    KNOWLEDGE_STORAGE_PATH: str = "./data/knowledge"
    S3_ENDPOINT_URL: str = ""
    S3_BUCKET: str = "infopulse-knowledge"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"
    KNOWLEDGE_MAX_FILE_MB: int = 25
    KNOWLEDGE_MAX_FILES_PER_UPLOAD: int = 10
    KNOWLEDGE_WEB_MAX_BYTES: int = 5_000_000

    @field_validator("CORS_ORIGINS", "TRUSTED_HOSTS", "ADMIN_EMAILS", mode="before")
    @classmethod
    def parse_csv(cls, value):
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def production_errors(self) -> list[str]:
        if self.ENVIRONMENT.lower() != "production":
            return []
        errors = []
        if self.JWT_SECRET_KEY.startswith("change-me") or len(self.JWT_SECRET_KEY) < 32:
            errors.append("JWT_SECRET_KEY must be a random value of at least 32 characters")
        if "sqlite" in self.DATABASE_URL.lower():
            errors.append("production DATABASE_URL must use PostgreSQL")
        if self.AUTO_CREATE_TABLES:
            errors.append("AUTO_CREATE_TABLES must be false in production")
        if self.RUN_BACKGROUND_WORKERS_IN_API:
            errors.append("RUN_BACKGROUND_WORKERS_IN_API must be false in production")
        if not self.CORS_ORIGINS or "*" in self.CORS_ORIGINS:
            errors.append("CORS_ORIGINS must contain explicit origins")
        if not self.TRUSTED_HOSTS or "*" in self.TRUSTED_HOSTS:
            errors.append("TRUSTED_HOSTS must contain explicit hosts")
        if not self.ADMIN_EMAILS:
            errors.append("ADMIN_EMAILS must contain at least one administrator")
        if len(self.METRICS_TOKEN) < 24:
            errors.append("METRICS_TOKEN must contain at least 24 characters")
        return errors

    def assert_production_ready(self) -> None:
        errors = self.production_errors()
        if errors:
            raise RuntimeError("Invalid production configuration: " + "; ".join(errors))

    # --- Third-party APIs ---
    GITHUB_TOKEN: str = ""

    # --- Crawler ---
    CRAWLER_HEADLESS: bool = True
    CRAWLER_REQUEST_INTERVAL_MIN: float = 2.0
    CRAWLER_REQUEST_INTERVAL_MAX: float = 5.0
    BROWSER_RESTART_MB: int = 800
    WEIBO_COOKIE: str = ""
    TIEBA_COOKIE: str = ""

    # --- Demo Mode ---
    DEMO_MODE: bool = False
    CRAWLER_ENABLED: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance (singleton)."""
    return Settings()

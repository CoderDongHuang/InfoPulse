"""
InfoPulse — Application Configuration
======================================
All settings read from environment variables / .env file.
Uses pydantic-settings for validation and auto-loading.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

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
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    WEBHOOK_TIMEOUT_SECONDS: int = 10

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

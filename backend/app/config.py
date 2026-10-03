from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PROJECT_NAME: str = "Audio Notes Platform"
    API_V1_PREFIX: str = "/api"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./audionotes.db",
        description="Database connection URL. Defaults to SQLite for local development, or PostgreSQL in production."
    )

    # Redis for Background Jobs
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for task queue."
    )
    REQUIRE_REDIS_QUEUE: bool = Field(
        default=False,
        description="Fail uploads when Redis/RQ is unavailable instead of using the local development thread fallback."
    )
    RQ_JOB_TIMEOUT_SECONDS: int = 3600

    # Gnani ASR Credentials
    GNANI_API_KEY: str = Field(
        default="",
        description="Gnani ASR API key (Passed via X-API-Key-ID header)."
    )
    GNANI_API_BASE_URL: str = Field(
        default="https://api.vachana.ai",
        description="Gnani STT API base URL."
    )
    DEFAULT_LANGUAGE: str = "en-IN"

    # Storage Provider: "local" or "s3"
    STORAGE_PROVIDER: str = "local"
    STORAGE_LOCAL_DIR: str = "storage"
    STORAGE_BUCKET: str = "audionotes"
    STORAGE_ENDPOINT: Optional[str] = None
    STORAGE_ACCESS_KEY: Optional[str] = None
    STORAGE_SECRET_KEY: Optional[str] = None
    STORAGE_REGION: str = "us-east-1"

    # Google Gemini Summarization
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Gemini API key for transcript summarization."
    )
    GEMINI_MODEL: str = Field(
        default="gemini-3.5-flash-lite",
        description="Google Gemini model identifier (e.g. gemini-3.5-flash-lite, gemini-3.5-flash)."
    )

    # Legacy / Alternative LLM Summarization
    LLM_PROVIDER: str = "gemini"  # "gemini", "openai", "groq", or "fallback"
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_BASE_URL: str = "https://api.openai.com/v1"

    # Limits & Security
    MAX_UPLOAD_SIZE_MB: int = 100
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]


settings = Settings()

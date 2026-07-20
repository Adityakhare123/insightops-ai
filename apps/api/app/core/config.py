from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    project_name: str = "InsightOps AI"
    environment: str = "development"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_port: int = 5173

    # PostgreSQL
    postgres_db: str = "insightops"
    postgres_user: str = "insightops"
    postgres_password: str = "change_me"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    database_url: str = (
        "postgresql+psycopg://"
        "insightops:change_me@postgres:5432/insightops"
    )

    # Redis and Celery
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "insightops"
    minio_secret_key: str = "change_me_minio"
    minio_bucket: str = "insightops-documents"
    minio_secure: bool = False

    # Authentication
    jwt_secret_key: str = Field(
        default="replace_with_a_secure_secret",
        min_length=16,
    )

    jwt_algorithm: str = "HS256"

    access_token_expire_minutes: int = Field(
        default=60,
        ge=1,
    )

    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
    )

    # Demo administrator
    demo_workspace_slug: str = Field(
        default="insightops-insurance-demo",
        min_length=2,
        max_length=100,
    )

    demo_admin_email: str = Field(
        default="admin@insightops.ai",
        min_length=3,
        max_length=255,
    )

    demo_admin_full_name: str = Field(
        default="InsightOps Administrator",
        min_length=2,
        max_length=150,
    )

    demo_admin_password: str = Field(
        default="InsightOpsAdmin123!",
        min_length=8,
        max_length=128,
    )

    # Frontend
    vite_api_base_url: str = (
        "http://localhost:8000/api/v1"
    )

    # CORS
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached application settings instance."""

    return Settings()


settings = get_settings()
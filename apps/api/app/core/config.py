from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    project_name: str = "InsightOps AI"
    environment: str = "development"

    database_url: str = (
        "postgresql+psycopg://insightops:change_me@postgres:5432/insightops"
    )
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "insightops"
    minio_secret_key: str = "change_me_minio"
    minio_bucket: str = "insightops-documents"
    minio_secure: bool = False

    jwt_secret_key: str = Field(default="replace_me", min_length=8)
    jwt_algorithm: str = "HS256"

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

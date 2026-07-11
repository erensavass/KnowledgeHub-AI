from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Typed configuration sourced from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Enterprise RAG Assistant", validation_alias="APP_NAME")
    app_environment: Environment = Field(
        default=Environment.DEVELOPMENT, validation_alias="APP_ENVIRONMENT"
    )
    app_debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: PositiveInt = Field(default=8000, validation_alias="APP_PORT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    secret_key: SecretStr = Field(validation_alias="SECRET_KEY", min_length=32)
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: PositiveInt = Field(
        default=30, validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    database_url: str = Field(
        default="postgresql+psycopg://enterprise_rag:change-me-before-production@db:5432/enterprise_rag",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://redis:6379/0", validation_alias="REDIS_URL")
    document_storage_path: Path = Field(
        default=Path("/data/documents"), validation_alias="DOCUMENT_STORAGE_PATH"
    )
    max_upload_size_mb: PositiveInt = Field(default=20, validation_alias="MAX_UPLOAD_SIZE_MB")


@lru_cache
def get_settings() -> Settings:
    return Settings()

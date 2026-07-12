from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, NonNegativeInt, PositiveInt, SecretStr, field_validator, model_validator
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
    app_version: str = Field(default="0.4.0", validation_alias="APP_VERSION")
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
    chunk_size: PositiveInt = Field(default=1000, validation_alias="CHUNK_SIZE")
    chunk_overlap: NonNegativeInt = Field(default=150, validation_alias="CHUNK_OVERLAP")
    embedding_model: str = Field(default="BAAI/bge-m3", validation_alias="EMBEDDING_MODEL")
    embedding_device: str = Field(default="cpu", validation_alias="EMBEDDING_DEVICE")
    embedding_batch_size: PositiveInt = Field(
        default=32, validation_alias="EMBEDDING_BATCH_SIZE"
    )
    embedding_dimension: PositiveInt = Field(default=1024, validation_alias="EMBEDDING_DIMENSION")
    milvus_uri: str = Field(default="http://milvus:19530", validation_alias="MILVUS_URI")
    milvus_token: str = Field(default="", validation_alias="MILVUS_TOKEN")
    milvus_collection: str = Field(
        default="knowledgehub_chunks", validation_alias="MILVUS_COLLECTION"
    )
    milvus_metric_type: str = Field(default="COSINE", validation_alias="MILVUS_METRIC_TYPE")
    milvus_index_type: str = Field(default="HNSW", validation_alias="MILVUS_INDEX_TYPE")
    milvus_hnsw_m: PositiveInt = Field(default=16, validation_alias="MILVUS_HNSW_M")
    milvus_hnsw_ef_construction: PositiveInt = Field(
        default=200, validation_alias="MILVUS_HNSW_EF_CONSTRUCTION"
    )
    search_default_top_k: PositiveInt = Field(default=5, validation_alias="SEARCH_DEFAULT_TOP_K")
    search_max_top_k: PositiveInt = Field(default=20, validation_alias="SEARCH_MAX_TOP_K")
    search_score_threshold: float = Field(
        default=0.0, validation_alias="SEARCH_SCORE_THRESHOLD"
    )

    @field_validator(
        "embedding_model",
        "embedding_device",
        "milvus_uri",
        "milvus_collection",
        "milvus_index_type",
    )
    @classmethod
    def validate_embedding_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("embedding configuration values must not be blank")
        return value

    @field_validator("milvus_metric_type")
    @classmethod
    def validate_metric(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in {"COSINE", "IP", "L2"}:
            raise ValueError("MILVUS_METRIC_TYPE must be COSINE, IP, or L2")
        return value

    @model_validator(mode="after")
    def validate_chunk_settings(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if self.search_default_top_k > self.search_max_top_k:
            raise ValueError("SEARCH_DEFAULT_TOP_K must not exceed SEARCH_MAX_TOP_K")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

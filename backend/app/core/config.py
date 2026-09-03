from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "AI Knowledge Assistant"
    app_version: str = "0.1.0"
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    enable_docs: bool = True
    expose_error_details: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    rate_limit_enabled: bool = False
    rate_limit_requests: int = Field(default=120, ge=1, le=10_000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    # Local HTTP/SSH tunnel only. Set true before using a public HTTPS endpoint.
    auth_cookie_secure: bool = False

    database_url: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/knowledge"
    )

    document_storage_path: Path = PROJECT_ROOT / "data" / "documents"
    max_upload_size_mb: int = Field(default=100, ge=1, le=1024)
    allowed_document_extensions: tuple[str, ...] = (
        ".txt",
        ".md",
        ".pdf",
        ".docx",
    )

    chunk_size: int = 1000
    chunk_overlap: int = 150

    document_parser: Literal["local", "mineru", "auto"] = "auto"
    mineru_api_token: SecretStr = SecretStr("")
    mineru_base_url: str = "https://mineru.net/api/v4"
    mineru_model_version: Literal["pipeline", "vlm"] = "vlm"
    mineru_enable_ocr: bool = True
    mineru_enable_table: bool = True
    mineru_enable_formula: bool = True
    mineru_poll_interval_seconds: float = Field(default=3.0, gt=0)
    mineru_timeout_seconds: int = Field(default=600, ge=30, le=3600)
    background_worker_count: int = Field(default=3, ge=1, le=16)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    milvus_uri: str = "http://localhost:19530"
    milvus_token: SecretStr = SecretStr("")
    milvus_collection_name: str = "document_chunks"

    deepseek_api_key: SecretStr = SecretStr("")
    deepseek_base_url: str = "https://api.deepseek.com"
    chat_model: str = "deepseek-v4-flash"
    chat_temperature: float = 0.2
    chat_max_tokens: int = 2048
    conversation_history_limit: int = Field(
        default=10,
        ge=2,
        le=100,
    )
    embedding_provider: str = "siliconflow"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 32

    siliconflow_api_key: SecretStr = SecretStr("")
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @staticmethod
    def secret_value(value: SecretStr) -> str:
        return value.get_secret_value().strip()

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if not self.is_production:
            return self

        errors: list[str] = []
        if self.debug:
            errors.append("DEBUG must be false")
        if self.enable_docs:
            errors.append("ENABLE_DOCS must be false")
        if self.expose_error_details:
            errors.append("EXPOSE_ERROR_DETAILS must be false")
        if not self.rate_limit_enabled:
            errors.append("RATE_LIMIT_ENABLED must be true")
        if "*" in self.cors_origins:
            errors.append("CORS_ORIGINS cannot contain '*'")
        if "*" in self.trusted_hosts:
            errors.append("TRUSTED_HOSTS cannot contain '*'")
        if "postgres:postgres@" in self.database_url.lower():
            errors.append("DATABASE_URL cannot use the default password")
        if not self.secret_value(self.deepseek_api_key):
            errors.append("DEEPSEEK_API_KEY is required")
        if not self.secret_value(self.siliconflow_api_key):
            errors.append("SILICONFLOW_API_KEY is required")

        if errors:
            raise ValueError(
                "Invalid production configuration: " + "; ".join(errors)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

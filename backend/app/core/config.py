from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "AI Knowledge Assistant"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/knowledge"
    )

    document_storage_path: Path = PROJECT_ROOT / "data" / "documents"
    max_upload_size_mb: int = 20
    allowed_document_extensions: tuple[str, ...] = (
        ".txt",
        ".md",
        ".pdf",
        ".docx",
    )

    chunk_size: int = 1000
    chunk_overlap: int = 150

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = ""
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = ""
    milvus_collection_name: str = "document_chunks"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    chat_model: str = "deepseek-v4-flash"
    embedding_provider: str = "siliconflow"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 32

    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
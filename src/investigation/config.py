"""Validated configuration. Secrets are never included in diagnostics."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "Investigation Engine"
    environment: Literal["local", "test", "production"] = "local"
    data_dir: Path = Path("data")
    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    collection_prefix: str = "investigation"
    embedding_backend: Literal["fastembed", "hash"] = "fastembed"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = Field(default=384, ge=16)
    embedding_batch_size: int = Field(default=64, ge=1, le=512)
    embedding_threads: int = Field(default=2, ge=1, le=32)
    chunk_strategy: Literal["fixed", "structure"] = "structure"
    chunk_tokens: int = Field(default=256, ge=32, le=1024)
    chunk_overlap: int = Field(default=40, ge=0)
    bm25_avg_length: float = Field(default=150.0, gt=0)
    retrieval_limit: int = Field(default=30, ge=5, le=100)
    evidence_limit: int = Field(default=12, ge=2, le=30)
    retrieval_mode: Literal["dense", "sparse", "hybrid"] = "hybrid"
    reranker_enabled: bool = True
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    reranker_batch_size: int = Field(default=4, ge=1, le=32)
    llm_provider: Literal["gemini", "ollama", "extractive"] = "extractive"
    llm_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: SecretStr | None = None
    ollama_url: str = "http://localhost:11434"
    llm_timeout_seconds: float = Field(default=60, gt=0, le=180)
    llm_max_retries: int = Field(default=2, ge=0, le=4)
    llm_input_usd_per_million: float = Field(default=0, ge=0)
    llm_output_usd_per_million: float = Field(default=0, ge=0)
    max_tool_calls: int = Field(default=6, ge=1, le=12)
    max_subquestions: int = Field(default=4, ge=1, le=6)
    max_context_chars: int = Field(default=22000, ge=2000, le=80000)
    min_dense_score: float = Field(default=0.25, ge=0, le=1)
    cache_ttl_seconds: int = Field(default=600, ge=0)
    admin_token: SecretStr | None = None
    max_upload_mb: int = Field(default=10, ge=1, le=30)
    requests_per_minute: int = Field(default=12, ge=1, le=120)
    max_concurrent_investigations: int = Field(default=2, ge=1, le=8)
    allow_origins: list[str] = []

    @model_validator(mode="after")
    def validate_configuration(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_tokens:
            raise ValueError("CHUNK_OVERLAP must be less than CHUNK_TOKENS")
        if self.environment == "production" and not self.admin_token:
            raise ValueError("ADMIN_TOKEN is required in production to protect document mutations")
        if self.environment == "production" and not self.qdrant_url:
            raise ValueError("QDRANT_URL is required in production for persistent external storage")
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for LLM_PROVIDER=gemini")
        if self.environment == "production" and self.embedding_backend == "hash":
            raise ValueError("Hash embeddings are test fixtures, not semantic embeddings")
        return self

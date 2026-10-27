"""Public application contracts shared by ingestion, retrieval, API and evaluation."""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SourceLocation(BaseModel):
    page: int | None = None
    section: str | None = None
    start_char: int = 0
    end_char: int = 0
    sentence_ids: list[int] = []


class TextBlock(BaseModel):
    text: str
    location: SourceLocation = Field(default_factory=SourceLocation)


class ParsedDocument(BaseModel):
    title: str
    text: str
    blocks: list[TextBlock] = []
    metadata: dict[str, Any] = {}


class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    revision: int = 1
    title: str
    filename: str
    format: str
    source_uri: str | None = None
    checksum: str
    text: str
    blocks: list[TextBlock] = []
    metadata: dict[str, Any] = {}
    status: Literal["processing", "ready", "failed", "deleted"] = "processing"
    chunk_count: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class Chunk(BaseModel):
    id: str
    document_id: str
    revision: int
    title: str
    text: str
    checksum: str
    location: SourceLocation = Field(default_factory=SourceLocation)
    metadata: dict[str, Any] = {}
    strategy: str = "structure"


class IngestionResult(BaseModel):
    status: Literal["created", "updated", "duplicate", "near_duplicate"]
    document: Document
    duplicate_of: str | None = None
    warnings: list[str] = []


class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: Literal["queued", "running", "complete", "failed"] = "queued"
    total: int = 0
    processed: int = 0
    failed: int = 0
    message: str = ""
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    metadata: dict[str, Any] = {}


class SearchFilters(BaseModel):
    document_ids: list[str] = []
    dataset: str | None = None
    source_type: str | None = None
    revision: int | None = None


class SearchHit(BaseModel):
    chunk: Chunk
    score: float
    dense_score: float | None = None
    sparse_score: float | None = None
    rerank_score: float | None = None
    channels: list[str] = []
    subquestions: list[int] = []


class InvestigationRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    mode: Literal["dense", "sparse", "hybrid"] | None = None
    rerank: bool | None = None
    use_cache: bool = True

    @field_validator("question", mode="before")
    @classmethod
    def normalize_question(cls, value):
        return value.strip() if isinstance(value, str) else value


class InvestigationPlan(BaseModel):
    kind: Literal["direct", "comparison", "multi_hop", "unknown"] = "direct"
    subquestions: list[str] = Field(min_length=1, max_length=6)
    rationale: str = ""


class Citation(BaseModel):
    id: str
    passage_id: str
    document_id: str
    revision: int
    title: str
    quote: str
    location: SourceLocation
    source_uri: str | None = None


class Claim(BaseModel):
    text: str
    citation_ids: list[str] = []
    supported: bool = True


class Conflict(BaseModel):
    description: str
    citation_ids: list[str] = []


class TraceStep(BaseModel):
    stage: str
    detail: str
    duration_ms: float = 0
    metadata: dict[str, Any] = {}


class InvestigationAnswer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    question: str
    status: Literal["answered", "insufficient_evidence", "conflicting_evidence", "error"]
    answer: str
    claims: list[Claim] = []
    citations: list[Citation] = []
    conflicts: list[Conflict] = []
    plan: InvestigationPlan
    trace: list[TraceStep] = []
    retrieved_passage_ids: list[str] = []
    retrieved_document_ids: list[str] = []
    model: str
    provider: str
    corpus_revision: str
    elapsed_ms: float = 0
    usage: dict[str, int | float] = {}
    cached: bool = False
    warnings: list[str] = []

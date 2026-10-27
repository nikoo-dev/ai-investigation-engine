"""Persistent Qdrant repositories for documents, passages, jobs and corpus state.

The document row is the publication marker for a revision. Queries validate every
candidate against that marker, so a failed replacement cannot expose half an update.
Qdrant's local client is useful for development; a server is required for sharing a
database between processes. All calls through this Store are serialized locally.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Sequence
from contextlib import suppress
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from qdrant_client import QdrantClient, models

from investigation.config import Settings
from investigation.models import Chunk, Document, Job, SearchFilters, SearchHit, utc_now


def point_id(value: str) -> str:
    """Qdrant IDs must be UUIDs or unsigned integers; accept stable external IDs."""
    try:
        from uuid import UUID

        return str(UUID(value))
    except ValueError:
        return str(uuid5(NAMESPACE_URL, value))


class Store:
    def __init__(self, settings: Settings, dimension: int):
        self.settings = settings
        self.dimension = dimension
        self.lock = threading.RLock()
        self._corpus_dirty = False
        prefix = settings.collection_prefix
        self.chunks_collection = f"{prefix}_chunks"
        self.documents_collection = f"{prefix}_documents"
        self.jobs_collection = f"{prefix}_jobs"
        self.meta_collection = f"{prefix}_metadata"
        if settings.qdrant_url:
            self.client = QdrantClient(
                url=settings.qdrant_url,
                api_key=(
                    settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
                ),
                timeout=60,
            )
        else:
            directory = settings.data_dir / "qdrant"
            directory.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(directory), force_disable_check_same_thread=True)
        try:
            self._initialize()
        except Exception:
            self.client.close()
            raise

    def _initialize(self) -> None:
        with self.lock:
            for name in [self.documents_collection, self.jobs_collection, self.meta_collection]:
                if not self.client.collection_exists(name):
                    self.client.create_collection(name, vectors_config={})
            if not self.client.collection_exists(self.chunks_collection):
                self.client.create_collection(
                    self.chunks_collection,
                    vectors_config={
                        "dense": models.VectorParams(
                            size=self.dimension, distance=models.Distance.COSINE, on_disk=True
                        )
                    },
                    sparse_vectors_config={
                        "sparse": models.SparseVectorParams(
                            modifier=models.Modifier.IDF,
                            index=models.SparseIndexParams(on_disk=True),
                        )
                    },
                    on_disk_payload=True,
                )
            info = self.client.get_collection(self.chunks_collection)
            vectors = info.config.params.vectors
            if (
                not isinstance(vectors, dict)
                or "dense" not in vectors
                or vectors["dense"].size != self.dimension
            ):
                raise ValueError(
                    "Existing vector dimensions do not match the embedding model; use a new COLLECTION_PREFIX"
                )
            signature = f"{self.settings.embedding_backend}:{self.settings.embedding_model}:{self.dimension}"
            existing = self.get_metadata("embedding_signature")
            if existing and existing.get("value") != signature:
                raise ValueError(
                    "Existing collection uses a different embedding model; use a new COLLECTION_PREFIX"
                )
            if not existing:
                self.put_metadata("embedding_signature", {"value": signature})
            ingestion_options = {
                "strategy": self.settings.chunk_strategy,
                "size": self.settings.chunk_tokens,
                "overlap": self.settings.chunk_overlap,
                "bm25_avg_length": self.settings.bm25_avg_length,
                "pipeline": "model-token-offsets-title-prefix-v2",
            }
            ingestion_signature = hashlib.sha256(
                json.dumps(ingestion_options, sort_keys=True).encode()
            ).hexdigest()
            previous_options = self.get_metadata("ingestion_signature")
            if previous_options and previous_options.get("value") != ingestion_signature:
                raise ValueError(
                    "Existing collection uses different ingestion/chunking settings; use a new COLLECTION_PREFIX"
                )
            if not previous_options:
                if self.client.count(self.chunks_collection, exact=True).count:
                    raise ValueError(
                        "Existing collection predates versioned chunking; reindex with a new COLLECTION_PREFIX"
                    )
                self.put_metadata(
                    "ingestion_signature",
                    {"value": ingestion_signature, "options": ingestion_options},
                )
            if not self.get_metadata("corpus_revision"):
                self.put_metadata("corpus_revision", {"value": "empty"})
            if self.settings.qdrant_url:
                for name, key, schema in [
                    (self.documents_collection, "checksum", models.PayloadSchemaType.KEYWORD),
                    (self.documents_collection, "status", models.PayloadSchemaType.KEYWORD),
                    (self.chunks_collection, "document_id", models.PayloadSchemaType.KEYWORD),
                    (self.chunks_collection, "revision", models.PayloadSchemaType.INTEGER),
                    (self.chunks_collection, "metadata.dataset", models.PayloadSchemaType.KEYWORD),
                    (
                        self.chunks_collection,
                        "metadata.source_type",
                        models.PayloadSchemaType.KEYWORD,
                    ),
                ]:
                    self.client.create_payload_index(name, key, field_schema=schema, wait=True)

    def put_metadata(self, key: str, value: dict[str, Any]) -> None:
        with self.lock:
            self.client.upsert(
                self.meta_collection,
                [models.PointStruct(id=point_id(key), vector={}, payload=value)],
                wait=True,
            )

    def get_metadata(self, key: str) -> dict[str, Any] | None:
        with self.lock:
            records = self.client.retrieve(self.meta_collection, [point_id(key)], with_payload=True)
            return dict(records[0].payload or {}) if records else None

    def _touch(self) -> None:
        self.put_metadata("corpus_revision", {"value": str(uuid4()), "updated_at": utc_now()})
        self._corpus_dirty = False

    def corpus_revision(self) -> str:
        with self.lock:
            if self._corpus_dirty:
                self._touch()
            value = self.get_metadata("corpus_revision")
            return str(value["value"]) if value else "empty"

    def put_document(self, doc: Document) -> None:
        with self.lock:
            self._corpus_dirty = True
            self.client.upsert(
                self.documents_collection,
                [
                    models.PointStruct(
                        id=point_id(doc.id), vector={}, payload=doc.model_dump(mode="json")
                    )
                ],
                wait=True,
            )
            self._touch()

    def put_documents(self, docs: Sequence[Document]) -> None:
        """Publish a completed batch; readers still check each document revision."""
        if not docs:
            return
        with self.lock:
            self._corpus_dirty = True
            self.client.upsert(
                self.documents_collection,
                [
                    models.PointStruct(
                        id=point_id(doc.id), vector={}, payload=doc.model_dump(mode="json")
                    )
                    for doc in docs
                ],
                wait=True,
            )
            self._touch()

    def get_documents(self, document_ids: Sequence[str]) -> dict[str, Document]:
        if not document_ids:
            return {}
        with self.lock:
            records = self.client.retrieve(
                self.documents_collection,
                [point_id(x) for x in dict.fromkeys(document_ids)],
                with_payload=True,
            )
            documents = [
                Document.model_validate(record.payload) for record in records if record.payload
            ]
            return {doc.id: doc for doc in documents if doc.status != "deleted"}

    def get_document(self, document_id: str) -> Document | None:
        return self.get_documents([document_id]).get(document_id)

    def list_documents(self, limit: int = 50, offset: int = 0) -> list[Document]:
        """Stable UUID ordering with bounded page size; offset is a UI cursor index."""
        if limit < 1 or offset < 0:
            return []
        with self.lock:
            records, cursor = self.client.scroll(
                self.documents_collection,
                scroll_filter=models.Filter(
                    must_not=[
                        models.FieldCondition(
                            key="status", match=models.MatchValue(value="deleted")
                        )
                    ]
                ),
                limit=min(256, max(limit, 1)),
                with_payload=True,
            )
            skipped = 0
            results: list[Document] = []
            while True:
                for record in records:
                    if skipped < offset:
                        skipped += 1
                        continue
                    if record.payload:
                        results.append(Document.model_validate(record.payload))
                    if len(results) >= limit:
                        return results
                if cursor is None:
                    break
                records, cursor = self.client.scroll(
                    self.documents_collection,
                    scroll_filter=models.Filter(
                        must_not=[
                            models.FieldCondition(
                                key="status", match=models.MatchValue(value="deleted")
                            )
                        ]
                    ),
                    limit=256,
                    offset=cursor,
                    with_payload=True,
                )
            return results

    def find_checksum(self, checksum: str, exclude_id: str | None = None) -> Document | None:
        with self.lock:
            records, _ = self.client.scroll(
                self.documents_collection,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="checksum", match=models.MatchValue(value=checksum)
                        ),
                        models.FieldCondition(key="status", match=models.MatchValue(value="ready")),
                    ]
                ),
                limit=10,
                with_payload=True,
            )
            for record in records:
                doc = Document.model_validate(record.payload)
                if doc.id != exclude_id:
                    return doc
            return None

    def document_checksums(self) -> dict[str, str]:
        """Read a compact deduplication manifest once for a bulk import."""
        result: dict[str, str] = {}
        cursor = None
        with self.lock:
            while True:
                records, cursor = self.client.scroll(
                    self.documents_collection,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="status", match=models.MatchValue(value="ready")
                            )
                        ]
                    ),
                    limit=1000,
                    offset=cursor,
                    with_payload=["id", "checksum"],
                )
                for record in records:
                    value = record.payload or {}
                    if value.get("checksum") and value.get("id"):
                        result[str(value["checksum"])] = str(value["id"])
                if cursor is None:
                    return result

    def upsert_chunks(
        self, chunks: list[Chunk], dense: list[list[float]], sparse: list[dict[str, Any]]
    ) -> None:
        if not (len(chunks) == len(dense) == len(sparse)):
            raise ValueError("Chunk/vector counts differ")
        with self.lock:
            for start in range(0, len(chunks), 128):
                points = [
                    models.PointStruct(
                        id=point_id(chunk.id),
                        vector={"dense": vector, "sparse": models.SparseVector(**lexical)},
                        payload=chunk.model_dump(mode="json"),
                    )
                    for chunk, vector, lexical in zip(
                        chunks[start : start + 128],
                        dense[start : start + 128],
                        sparse[start : start + 128],
                        strict=True,
                    )
                ]
                if points:
                    self.client.upsert(self.chunks_collection, points, wait=True)

    def commit_document(
        self,
        doc: Document,
        chunks: list[Chunk],
        dense: list[list[float]],
        sparse: list[dict[str, Any]],
    ) -> None:
        """Index first, publish second, then remove the previously visible revision."""
        with self.lock:
            old = self.get_document(doc.id)
            try:
                self.upsert_chunks(chunks, dense, sparse)
                self.put_document(doc)
            except Exception:
                # An acknowledged timeout may occur after Qdrant committed the
                # document marker. Never delete a revision that is now visible.
                published = None
                checked = False
                with suppress(Exception):
                    published = self.get_document(doc.id)
                    checked = True
                if (
                    published is not None
                    and published.revision == doc.revision
                    and published.checksum == doc.checksum
                ):
                    raise
                if checked and (published is not None or old is None):
                    with suppress(Exception):
                        self.delete_chunks(doc.id, revision=doc.revision)
                raise
            if old is not None and old.revision != doc.revision:
                self.delete_chunks(doc.id, revision=old.revision)

    def _filter(self, filters: SearchFilters) -> models.Filter | None:
        conditions: list[Any] = []
        if filters.document_ids:
            conditions.append(
                models.FieldCondition(
                    key="document_id", match=models.MatchAny(any=filters.document_ids)
                )
            )
        if filters.dataset:
            conditions.append(
                models.FieldCondition(
                    key="metadata.dataset", match=models.MatchValue(value=filters.dataset)
                )
            )
        if filters.source_type:
            conditions.append(
                models.FieldCondition(
                    key="metadata.source_type", match=models.MatchValue(value=filters.source_type)
                )
            )
        if filters.revision is not None:
            conditions.append(
                models.FieldCondition(
                    key="revision", match=models.MatchValue(value=filters.revision)
                )
            )
        return models.Filter(must=conditions) if conditions else None

    def _query(
        self, vector: Any, channel: str, limit: int, filters: SearchFilters
    ) -> list[SearchHit]:
        with self.lock:
            candidates = self.client.query_points(
                collection_name=self.chunks_collection,
                query=vector,
                using=channel,
                query_filter=self._filter(filters),
                limit=min(max(limit * 4, limit), 1000),
                with_payload=True,
            ).points
            docs = self.get_documents(
                [str((x.payload or {}).get("document_id", "")) for x in candidates]
            )
            results = []
            for candidate in candidates:
                if not candidate.payload:
                    continue
                chunk = Chunk.model_validate(candidate.payload)
                doc = docs.get(chunk.document_id)
                if not doc or doc.status != "ready" or doc.revision != chunk.revision:
                    continue
                results.append(
                    SearchHit(
                        chunk=chunk,
                        score=candidate.score,
                        dense_score=candidate.score if channel == "dense" else None,
                        sparse_score=candidate.score if channel == "sparse" else None,
                        channels=[channel],
                    )
                )
                if len(results) >= limit:
                    break
            return results

    def query_dense(
        self, vector: list[float], limit: int, filters: SearchFilters
    ) -> list[SearchHit]:
        return self._query(vector, "dense", limit, filters)

    def query_sparse(
        self, vector: dict[str, Any], limit: int, filters: SearchFilters
    ) -> list[SearchHit]:
        if not vector.get("indices"):
            return []
        return self._query(models.SparseVector(**vector), "sparse", limit, filters)

    def get_chunks(self, passage_ids: Sequence[str]) -> list[Chunk]:
        if not passage_ids:
            return []
        with self.lock:
            records = self.client.retrieve(
                self.chunks_collection, [point_id(x) for x in passage_ids], with_payload=True
            )
            chunks = [Chunk.model_validate(x.payload) for x in records if x.payload]
            docs = self.get_documents([x.document_id for x in chunks])
            available = {
                x.id: x
                for x in chunks
                if x.document_id in docs
                and docs[x.document_id].status == "ready"
                and docs[x.document_id].revision == x.revision
            }
            return [available[key] for key in passage_ids if key in available]

    def delete_chunks(self, document_id: str, revision: int | None = None) -> None:
        conditions: list[Any] = [
            models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))
        ]
        if revision is not None:
            conditions.append(
                models.FieldCondition(key="revision", match=models.MatchValue(value=revision))
            )
        with self.lock:
            self.client.delete(
                self.chunks_collection,
                models.FilterSelector(filter=models.Filter(must=conditions)),
                wait=True,
            )

    def delete_document(self, document_id: str) -> bool:
        with self.lock:
            document = self.get_document(document_id)
            if not document:
                return False
            document.status = "deleted"
            document.updated_at = utc_now()
            document.text = ""
            document.blocks = []
            document.metadata = {"deleted_at": document.updated_at}
            document.title = "Deleted document"
            document.filename = ""
            document.source_uri = None
            document.checksum = ""
            document.chunk_count = 0
            self.put_document(document)
            self.delete_chunks(document_id)
            return True

    def put_job(self, job: Job) -> None:
        with self.lock:
            job.updated_at = utc_now()
            self.client.upsert(
                self.jobs_collection,
                [
                    models.PointStruct(
                        id=point_id(job.id), vector={}, payload=job.model_dump(mode="json")
                    )
                ],
                wait=True,
            )

    def get_job(self, job_id: str) -> Job | None:
        with self.lock:
            records = self.client.retrieve(
                self.jobs_collection, [point_id(job_id)], with_payload=True
            )
            return Job.model_validate(records[0].payload) if records else None

    def stats(self) -> dict[str, Any]:
        with self.lock:
            ready = models.Filter(
                must=[models.FieldCondition(key="status", match=models.MatchValue(value="ready"))]
            )
            return {
                "documents": self.client.count(
                    self.documents_collection, count_filter=ready, exact=True
                ).count,
                "chunks": self.client.count(self.chunks_collection, exact=True).count,
                "corpus_revision": self.corpus_revision(),
                "backend": "qdrant_remote" if self.settings.qdrant_url else "qdrant_local",
            }

    def close(self) -> None:
        with self.lock:
            self.client.close()

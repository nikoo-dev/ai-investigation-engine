"""Idempotent document ingestion and revision-safe publication."""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import unicodedata
from collections.abc import Callable, Iterable
from pathlib import PureWindowsPath
from typing import Any, Protocol
from uuid import uuid4

from investigation.chunking import chunk_document
from investigation.config import Settings
from investigation.errors import ConflictError, InvalidDocument, NotFound
from investigation.models import (
    Document,
    IngestionResult,
    SearchFilters,
    SourceLocation,
    TextBlock,
    utc_now,
)
from investigation.parsers import normalize_text, parse_document, safe_filename
from investigation.storage import Store, point_id

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    dimension: int
    fingerprint: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def sparse(self, texts: list[str], query: bool = False) -> list[dict[str, Any]]: ...


def content_checksum(text: str) -> str:
    """Whitespace/case changes alone do not create a new evidence source."""
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class Ingestor:
    def __init__(self, store: Store, embedder: EmbeddingProvider, settings: Settings):
        self.store = store
        self.embedder = embedder
        self.settings = settings
        self._write_lock = threading.RLock()

    def _vectors(self, chunks: list[Any]) -> tuple[list[list[float]], list[dict[str, Any]]]:
        dense_texts = [
            f"{chunk.metadata.get('embedding_title', chunk.title)}\n{chunk.text}"
            for chunk in chunks
        ]
        sparse_texts = [f"{chunk.title}\n{chunk.text}" for chunk in chunks]
        tokenizer = getattr(self.embedder, "token_spans", None)
        if tokenizer:
            maximum = self.embedder.max_content_tokens  # type: ignore[attr-defined]
            if any(len(tokenizer(text)) > maximum for text in dense_texts):
                raise InvalidDocument(
                    "A passage exceeds the model token budget; no truncated evidence was indexed"
                )
        return self.embedder.embed(dense_texts), self.embedder.sparse(sparse_texts)

    def _chunks(self, document: Document) -> list[Any]:
        tokenizer = getattr(self.embedder, "token_spans", None)
        size = self.settings.chunk_tokens
        title = document.title
        if tokenizer:
            maximum = self.embedder.max_content_tokens  # type: ignore[attr-defined]
            title_spans = tokenizer(title)
            reserve = min(64, max(1, maximum // 4))
            if len(title_spans) > reserve:
                title = title[: title_spans[reserve - 1][1]]
            size = min(size, maximum - len(tokenizer(title + "\n")) - 1)
            if size < 1:
                raise InvalidDocument("The embedding model has no token capacity for evidence text")
        chunks = chunk_document(
            document,
            strategy=self.settings.chunk_strategy,
            size=size,
            overlap=min(self.settings.chunk_overlap, size - 1),
            tokenizer=tokenizer,
        )
        for chunk in chunks:
            chunk.metadata["embedding_title"] = title
            chunk.metadata["chunk_token_budget"] = size
            chunk.metadata["chunk_tokenizer"] = (
                self.embedder.fingerprint if tokenizer else "unicode-word-punctuation-test-fixture"
            )
        return chunks

    def ingest(
        self,
        filename: str,
        content: bytes,
        document_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        source_uri: str | None = None,
    ) -> IngestionResult:
        filename = safe_filename(filename)
        parsed = parse_document(
            filename, content, max_bytes=self.settings.max_upload_mb * 1024 * 1024
        )
        with self._write_lock:
            old = self.store.get_document(document_id) if document_id else None
            if document_id and old is None:
                raise NotFound("The document to replace does not exist")
            checksum = content_checksum(parsed.text)
            if old and old.checksum == checksum:
                return IngestionResult(status="duplicate", document=old, duplicate_of=old.id)
            duplicate = self.store.find_checksum(checksum, exclude_id=document_id)
            if duplicate:
                return IngestionResult(
                    status="duplicate",
                    document=duplicate,
                    duplicate_of=duplicate.id,
                    warnings=[
                        "Identical normalized text is already indexed; its existing citations are reused."
                    ],
                )
            details = {
                **parsed.metadata,
                **(metadata or {}),
                "source_type": (metadata or {}).get("source_type", "upload"),
                "embedding_fingerprint": self.embedder.fingerprint,
            }
            document = Document(
                id=old.id if old else str(uuid4()),
                revision=old.revision + 1 if old else 1,
                title=parsed.title,
                filename=filename,
                format=PureWindowsPath(filename).suffix.lower().lstrip("."),
                source_uri=source_uri,
                checksum=checksum,
                text=parsed.text,
                blocks=parsed.blocks,
                metadata=details,
                status="ready",
                created_at=old.created_at if old else utc_now(),
            )
            chunks = self._chunks(document)
            if not chunks:
                raise InvalidDocument("The document contains no searchable text")
            dense, sparse = self._vectors(chunks)
            near = self._near_duplicate(document, dense[0]) if not old else None
            warnings: list[str] = []
            if near:
                document.metadata["near_duplicate_of"] = near
                for chunk in chunks:
                    chunk.metadata["near_duplicate_of"] = near
                warnings.append(
                    "A similar document exists. Both are retained because even small differences may be evidence."
                )
            document.chunk_count = len(chunks)
            self.store.commit_document(document, chunks, dense, sparse)
            return IngestionResult(
                status="updated" if old else ("near_duplicate" if near else "created"),
                document=document,
                duplicate_of=near,
                warnings=warnings,
            )

    def _near_duplicate(self, document: Document, vector: list[float]) -> str | None:
        hits = self.store.query_dense(vector, 3, SearchFilters())
        words = set(re.findall(r"\w+", document.text.casefold()))
        for hit in hits:
            if hit.score < 0.96:
                continue
            other = set(re.findall(r"\w+", hit.chunk.text.casefold()))
            union = words | other
            if union and len(words & other) / len(union) >= 0.8:
                return hit.chunk.document_id
        return None

    def _record_document(self, record: dict[str, Any], old: Document | None = None) -> Document:
        text = record.get("text")
        if not isinstance(text, str) or not normalize_text(text):
            raise InvalidDocument("Each record requires a nonempty string text field")
        text = normalize_text(text)
        if len(text) > 10_000_000:
            raise InvalidDocument("A record exceeds the extracted text limit")
        title = str(record.get("title") or "Untitled record")[:1000]
        metadata = dict(record.get("metadata") or {})
        source_id = str(record.get("id") or content_checksum(f"{title}\n{text}"))
        metadata.setdefault("source_record_id", source_id)
        metadata.setdefault("source_type", "dataset")
        metadata["embedding_fingerprint"] = self.embedder.fingerprint
        blocks: list[TextBlock] = []
        cursor = 0
        for index, sentence in enumerate(metadata.get("sentences", [])):
            if not isinstance(sentence, str) or not sentence.strip():
                continue
            position = text.find(sentence, cursor)
            if position < 0:
                position = text.find(sentence.strip(), cursor)
                sentence = sentence.strip()
            if position >= 0:
                blocks.append(
                    TextBlock(
                        text=sentence,
                        location=SourceLocation(
                            start_char=position,
                            end_char=position + len(sentence),
                            sentence_ids=[index],
                        ),
                    )
                )
                cursor = position + len(sentence)
        if not blocks:
            blocks = [
                TextBlock(text=text, location=SourceLocation(start_char=0, end_char=len(text)))
            ]
        else:
            # Labels are advisory: malformed/incomplete sentence metadata must
            # never make unlabeled source text disappear from the index.
            complete_blocks: list[TextBlock] = []
            previous_end = 0
            for block in blocks:
                gap_end = block.location.start_char
                if text[previous_end:gap_end].strip():
                    complete_blocks.append(
                        TextBlock(
                            text=text[previous_end:gap_end],
                            location=SourceLocation(start_char=previous_end, end_char=gap_end),
                        )
                    )
                complete_blocks.append(block)
                previous_end = block.location.end_char
            if text[previous_end:].strip():
                complete_blocks.append(
                    TextBlock(
                        text=text[previous_end:],
                        location=SourceLocation(start_char=previous_end, end_char=len(text)),
                    )
                )
            blocks = complete_blocks
        return Document(
            id=point_id(source_id),
            revision=old.revision + 1 if old else 1,
            title=title,
            filename=safe_filename(str(record.get("filename") or f"{source_id}.txt")),
            format="record",
            source_uri=record.get("source_uri"),
            checksum=content_checksum(text),
            text=text,
            blocks=blocks,
            metadata=metadata,
            status="ready",
            created_at=old.created_at if old else utc_now(),
        )

    def ingest_record(self, record: dict[str, Any]) -> IngestionResult:
        """Create/replace a stable source identity; deletion tombstones are final.

        Replaying a dataset cannot silently restore a deliberately deleted source.
        Restoring that content requires an explicitly new source identity.
        """
        source_id = str(
            record.get("id")
            or content_checksum(
                f"{record.get('title', 'Untitled record')}\n{record.get('text', '')}"
            )
        )
        with self._write_lock:
            old = self.store.get_documents([point_id(source_id)], include_deleted=True).get(
                point_id(source_id)
            )
            if old is not None and old.status == "deleted":
                raise ConflictError(
                    "This source was deleted. Use a new source identity to intentionally restore its content."
                )
            doc = self._record_document(record, old)
            if old and old.checksum == doc.checksum:
                return IngestionResult(status="duplicate", document=old, duplicate_of=old.id)
            duplicate = self.store.find_checksum(doc.checksum, exclude_id=doc.id)
            if duplicate:
                return IngestionResult(
                    status="duplicate", document=duplicate, duplicate_of=duplicate.id
                )
            chunks = self._chunks(doc)
            dense, sparse = self._vectors(chunks)
            doc.chunk_count = len(chunks)
            self.store.commit_document(doc, chunks, dense, sparse)
            return IngestionResult(status="updated" if old else "created", document=doc)

    def ingest_records(
        self,
        records: Iterable[dict[str, Any]],
        batch_size: int = 64,
        progress: Callable[[dict[str, int]], None] | None = None,
    ) -> dict[str, int]:
        """Batch import with resumability via stable source IDs and checksums.

        Completed batches are durable and can be replayed safely after interruption.
        Failed rows are counted/logged; a vector-store outage fails the operation
        rather than silently claiming successful ingestion.
        Deliberately deleted source identities remain tombstoned on replay; those
        rows count as failures and require a new identity for an intended restore.
        """
        if batch_size < 1 or batch_size > 512:
            raise ValueError("batch_size must be in 1..512")
        counts = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "duplicates": 0,
            "failed": 0,
            "chunks": 0,
        }
        with self._write_lock:
            checksums = self.store.document_checksums()
            batch: list[dict[str, Any]] = []
            for record in records:
                batch.append(record)
                if len(batch) >= batch_size:
                    self._ingest_batch(batch, checksums, counts)
                    if progress:
                        progress(counts.copy())
                    batch = []
            if batch:
                self._ingest_batch(batch, checksums, counts)
                if progress:
                    progress(counts.copy())
        return counts

    def _ingest_batch(
        self, batch: list[dict[str, Any]], checksums: dict[str, str], counts: dict[str, int]
    ) -> None:
        candidates: list[Document] = []
        seen_ids: dict[str, str] = {}
        for record in batch:
            counts["processed"] += 1
            try:
                doc = self._record_document(record)
                if doc.id in seen_ids:
                    if seen_ids[doc.id] != doc.checksum:
                        raise InvalidDocument(
                            "A batch contains a repeated source ID with different content"
                        )
                    counts["duplicates"] += 1
                    continue
                if doc.checksum in checksums:
                    counts["duplicates"] += 1
                    continue
                candidates.append(doc)
                seen_ids[doc.id] = doc.checksum
            except (InvalidDocument, TypeError, ValueError) as exc:
                counts["failed"] += 1
                logger.warning("Skipping invalid source record: %s", exc)
        old_docs = self.store.get_documents([doc.id for doc in candidates], include_deleted=True)
        documents: list[Document] = []
        chunks = []
        pending_checksums: set[str] = set()
        for doc in candidates:
            if doc.checksum in pending_checksums:
                counts["duplicates"] += 1
                continue
            old = old_docs.get(doc.id)
            if old is not None and old.status == "deleted":
                counts["failed"] += 1
                logger.warning(
                    "Skipping deleted source identity; dataset replay does not restore tombstones"
                )
                continue
            if old:
                doc.revision = old.revision + 1
                doc.created_at = old.created_at
            parts = self._chunks(doc)
            if not parts:
                counts["failed"] += 1
                continue
            doc.chunk_count = len(parts)
            documents.append(doc)
            chunks.extend(parts)
            pending_checksums.add(doc.checksum)
        if not documents:
            return
        dense, sparse = self._vectors(chunks)
        with self.store.lock:
            self.store.validate_publication(documents)
            self.store.upsert_chunks(chunks, dense, sparse)
            self.store.put_documents(documents)
            for doc in documents:
                old = old_docs.get(doc.id)
                if old:
                    self.store.delete_chunks(doc.id, revision=old.revision)
                    counts["updated"] += 1
                else:
                    counts["created"] += 1
                checksums[doc.checksum] = doc.id
                if old and checksums.get(old.checksum) == doc.id:
                    checksums.pop(old.checksum, None)
                counts["chunks"] += doc.chunk_count


# Both spellings are kept to make the service role clear at call sites.
Ingestion = Ingestor

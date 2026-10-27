from uuid import uuid4

import pytest

from investigation.config import Settings
from investigation.embeddings import HashEmbedder
from investigation.ingestion import Ingestor
from investigation.models import SearchFilters
from investigation.storage import Store


@pytest.fixture
def components(tmp_path):
    settings = Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path,
        embedding_backend="hash",
        embedding_dimension=64,
        chunk_tokens=32,
        chunk_overlap=4,
        reranker_enabled=False,
    )
    embedder = HashEmbedder(dimension=64)
    store = Store(settings, embedder.dimension)
    yield settings, embedder, store, Ingestor(store, embedder, settings)
    store.close()


def test_document_lifecycle_revisions_filters_and_persistence(components):
    settings, embedder, store, ingest = components
    result = ingest.ingest(
        "facts.txt",
        b"Mars is the fourth planet. Red dust covers Mars.",
        metadata={"dataset": "planets", "source_type": "note"},
    )
    document_id = result.document.id
    revision_before = store.corpus_revision()
    hits = store.query_dense(
        embedder.embed(["Mars planet"])[0], 5, SearchFilters(dataset="planets")
    )
    assert hits and hits[0].chunk.document_id == document_id
    assert not store.query_dense(
        embedder.embed(["Mars planet"])[0], 5, SearchFilters(dataset="other")
    )
    lexical = store.query_sparse(embedder.sparse(["Mars"], query=True)[0], 5, SearchFilters())
    assert lexical and lexical[0].sparse_score is not None
    old_passage_id = hits[0].chunk.id
    update = ingest.ingest(
        "facts.txt",
        b"Jupiter is a gas giant. Its atmosphere contains hydrogen.",
        document_id=document_id,
    )
    assert update.document.revision == 2
    assert store.corpus_revision() != revision_before
    assert not store.get_chunks([old_passage_id])
    assert store.stats()["documents"] == 1
    store.close()
    reopened = Store(settings, embedder.dimension)
    try:
        assert reopened.get_document(document_id).revision == 2
        assert reopened.stats()["chunks"] == update.document.chunk_count
        assert reopened.delete_document(document_id)
        assert not reopened.get_document(document_id)
        assert not reopened.delete_document(document_id)
        assert not reopened.get_chunks([old_passage_id])
        assert reopened.stats()["documents"] == 0
        assert reopened.stats()["chunks"] == 0
    finally:
        reopened.close()


def test_unpublished_chunks_cannot_be_retrieved(components):
    _, embedder, store, ingest = components
    result = ingest.ingest("live.txt", b"The active evidence says the limit is 10.")
    old_doc = result.document
    unpublished = old_doc.model_copy(
        update={"revision": 2, "text": "The secret unpublished evidence says the limit is 50."}
    )
    chunks = ingest._chunks(unpublished)
    dense, sparse = ingest._vectors(chunks)
    store.upsert_chunks(chunks, dense, sparse)
    hits = store.query_dense(embedder.embed(["secret unpublished limit"])[0], 10, SearchFilters())
    assert all(hit.chunk.revision == 1 for hit in hits)
    assert store.get_chunks([chunk.id for chunk in chunks]) == []


def test_changed_model_same_dimensions_is_rejected(components):
    settings, embedder, store, _ = components
    store.close()
    changed = settings.model_copy(update={"embedding_model": "different-model"})
    with pytest.raises(ValueError, match="different embedding model"):
        Store(changed, embedder.dimension)
    restored = Store(settings, embedder.dimension)
    restored.close()


def test_chunking_configuration_is_not_silently_mixed(components):
    settings, embedder, store, _ = components
    store.close()
    changed = settings.model_copy(update={"chunk_strategy": "fixed"})
    with pytest.raises(ValueError, match="different ingestion/chunking settings"):
        Store(changed, embedder.dimension)


def test_failed_replacement_keeps_previous_revision(components, monkeypatch):
    _, _, store, ingest = components
    result = ingest.ingest("facts.txt", b"The existing statement is preserved.")
    old_revision = store.corpus_revision()

    def fail(_):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(store, "put_document", fail)
    with pytest.raises(RuntimeError, match="network unavailable"):
        ingest.ingest(
            "facts.txt",
            b"A replacement statement should not become visible.",
            document_id=result.document.id,
        )
    assert store.get_document(result.document.id).revision == 1
    assert store.corpus_revision() == old_revision
    assert store.stats()["chunks"] == result.document.chunk_count


def test_publication_timeout_does_not_destroy_committed_revision(components, monkeypatch):
    _, _, store, ingest = components
    original_touch = store._touch
    revision_before = store.corpus_revision()

    def fail_touch():
        raise RuntimeError("metadata timeout after publication")

    monkeypatch.setattr(store, "_touch", fail_touch)
    source_id = str(uuid4())
    with pytest.raises(RuntimeError, match="after publication"):
        ingest.ingest_record({"id": source_id, "text": "The committed evidence remains available."})
    assert store.get_document(source_id) is not None
    # Retrying generation invalidation repairs the cache key in the same process.
    monkeypatch.setattr(store, "_touch", original_touch)
    assert store.corpus_revision() != revision_before
    assert store.stats()["chunks"] == store.get_document(source_id).chunk_count


def test_record_id_preserved_and_idempotent_batch(components):
    _, _, store, ingest = components
    source_id = str(uuid4())
    records = [
        {"id": source_id, "title": "Sky", "text": "The sky is blue."},
        {"id": str(uuid4()), "title": "Water", "text": "Water is liquid at room temperature."},
    ]
    counts = ingest.ingest_records(records, batch_size=2)
    assert counts["created"] == 2
    assert store.get_document(source_id).id == source_id
    again = ingest.ingest_records(records, batch_size=2)
    assert again["duplicates"] == 2
    assert store.stats()["documents"] == 2

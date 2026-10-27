import pytest

from investigation.config import Settings
from investigation.embeddings import HashEmbedder
from investigation.ingestion import Ingestor
from investigation.models import Chunk, SearchFilters, SearchHit
from investigation.retrieval import Reranker, Retriever, diversify, reciprocal_rank_fusion
from investigation.storage import Store


def hit(identity, document=None, score=1.0, **overrides):
    return SearchHit(
        chunk=Chunk(
            id=identity,
            document_id=document or identity,
            revision=1,
            title=identity,
            text=f"Independent evidence passage {identity}.",
            checksum=identity,
        ),
        score=score,
        **overrides,
    )


def test_custom_rrf_formula_channel_merge_coverage_reward_and_stable_ties():
    first = hit("a", dense_score=0.8, channels=["dense"], subquestions=[0])
    second = hit("a", sparse_score=8, channels=["sparse"], subquestions=[1])
    rankings = [[first, hit("b")], [hit("b"), second]]
    fused = reciprocal_rank_fusion(rankings, weights=[2, 1], k=10)
    a = next(item for item in fused if item.chunk.id == "a")
    assert a.score == pytest.approx((2 / 11 + 1 / 12) * 1.08)
    assert a.channels == ["dense", "sparse"]
    assert a.dense_score == 0.8 and a.sparse_score == 8
    assert first.score == 1, "Fusion must not mutate caller-owned hit objects"
    tied = reciprocal_rank_fusion([[hit("b"), hit("a")], [hit("a"), hit("b")]])
    assert [item.chunk.id for item in tied] == ["a", "b"]


def test_duplicate_passage_cannot_inflate_its_rrf_contribution():
    fused = reciprocal_rank_fusion([[hit("a"), hit("a"), hit("b")]], k=10)
    assert len(fused) == 2
    assert fused[0].score == pytest.approx(1 / 11)
    assert fused[1].score == pytest.approx(1 / 13)
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[hit("a")]], weights=[-1])
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[hit("a")]], weights=[1, 1])


def test_rrf_preserves_zero_cosine_score_when_merging_lower_scores():
    fused = reciprocal_rank_fusion([[hit("a", dense_score=0)], [hit("a", dense_score=-0.2)]])
    assert fused[0].dense_score == 0


def test_document_diversity_is_soft_and_content_duplicates_are_removed():
    passages = [hit("a", "doc1", 1), hit("b", "doc1", 0.99), hit("c", "doc2", 0.9)]
    duplicate = hit("d", "doc3", 0.8)
    duplicate.chunk.checksum = "a"
    selected = diversify([*passages, duplicate], 10)
    assert [item.chunk.id for item in selected] == ["a", "c", "b"]
    assert len(diversify(passages, 1)) == 1
    assert passages[1].score == 0.99


def test_reranker_reorders_input_aligned_model_scores_without_mutating_hits(tmp_path):
    from types import SimpleNamespace

    settings = Settings(_env_file=None, environment="test", data_dir=tmp_path)
    reranker = Reranker(settings)
    reranker._model = SimpleNamespace(rerank=lambda query, texts, **kwargs: [-2.0, 2.0])
    passages = [hit("a"), hit("b")]
    result = reranker.rerank("Which source matters?", passages)
    assert [item.chunk.id for item in result] == ["b", "a"]
    assert result[0].rerank_score == 2 and result[0].score > result[1].score
    assert passages[0].rerank_score is None


def test_retrieval_cache_is_filter_bound_and_invalidated_by_document_delete(tmp_path):
    settings = Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path,
        embedding_backend="hash",
        embedding_dimension=64,
        chunk_tokens=64,
        chunk_overlap=8,
        reranker_enabled=False,
    )
    embedder = HashEmbedder(64)
    store = Store(settings, 64)
    try:
        ingest = Ingestor(store, embedder, settings)
        visible = ingest.ingest(
            "visible.txt",
            b"Atlas gateway timeout was 250 milliseconds.",
            metadata={"dataset": "visible"},
        )
        hidden = ingest.ingest(
            "hidden.txt",
            b"Atlas gateway timeout was 700 milliseconds.",
            metadata={"dataset": "hidden"},
        )
        retriever = Retriever(store, embedder, settings)
        filters = SearchFilters(dataset="visible")
        first = retriever.search("Atlas gateway timeout", filters)
        assert {item.chunk.document_id for item in first} == {visible.document.id}
        first[0].chunk.text = "Changed by caller"
        again = retriever.search("Atlas gateway timeout", filters)
        assert again[0].chunk.text != "Changed by caller"
        assert all(item.chunk.document_id != hidden.document.id for item in again)
        store.delete_document(visible.document.id)
        assert retriever.search("Atlas gateway timeout", filters) == []
    finally:
        store.close()

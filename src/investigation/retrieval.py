"""Custom rank fusion, document diversity, query coverage and ONNX cross-encoder reranking."""

import math
import threading
import time
from collections import Counter, OrderedDict, defaultdict
from typing import Any

from investigation.config import Settings
from investigation.embeddings import Embedder, fingerprint_json
from investigation.models import SearchFilters, SearchHit


def reciprocal_rank_fusion(
    rankings: list[list[SearchHit]], weights: list[float] | None = None, k: int = 60
) -> list[SearchHit]:
    """RRF combines ranks (not incomparable raw cosine/BM25 scores) with stable ties.

    Each result contributes at most once per ranking. Coverage rewards a passage seen
    for more than one subquestion; a bounded per-document penalty improves diversity.
    """
    weights = weights or [1.0] * len(rankings)
    if len(rankings) != len(weights) or k < 1 or any(w < 0 for w in weights):
        raise ValueError("RRF requires one non-negative weight per ranking and k >= 1")
    merged: dict[str, SearchHit] = {}
    scores: dict[str, float] = defaultdict(float)
    for ranking, weight in zip(rankings, weights, strict=True):
        seen = set()
        for rank, hit in enumerate(ranking, 1):
            key = hit.chunk.id
            if key in seen:
                continue
            seen.add(key)
            scores[key] += weight / (k + rank)
            if key not in merged:
                merged[key] = hit.model_copy(deep=True)
            else:
                current = merged[key]
                current.channels = sorted(set(current.channels + hit.channels))
                current.subquestions = sorted(set(current.subquestions + hit.subquestions))
                if hit.dense_score is not None:
                    current.dense_score = max(
                        current.dense_score if current.dense_score is not None else -1,
                        hit.dense_score,
                    )
                if hit.sparse_score is not None:
                    current.sparse_score = max(current.sparse_score or 0, hit.sparse_score)
    for key, hit in merged.items():
        hit.score = scores[key] * (1 + 0.08 * max(0, len(set(hit.subquestions)) - 1))
    return sorted(merged.values(), key=lambda h: (-h.score, h.chunk.id))


def diversify(hits: list[SearchHit], limit: int) -> list[SearchHit]:
    """Greedy soft document penalty; no hard cap that could erase necessary evidence."""
    remaining = [h.model_copy(deep=True) for h in hits]
    result: list[SearchHit] = []
    document_counts: Counter = Counter()
    checksums = set()
    while remaining and len(result) < limit:
        best = max(
            remaining, key=lambda h: h.score / (1 + 0.2 * document_counts[h.chunk.document_id])
        )
        remaining.remove(best)
        if best.chunk.checksum in checksums:
            continue
        checksums.add(best.chunk.checksum)
        result.append(best)
        document_counts[best.chunk.document_id] += 1
    return result


class Reranker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model: Any = None
        self._lock = threading.Lock()

    def rerank(self, question: str, hits: list[SearchHit]) -> list[SearchHit]:
        if not hits:
            return []
        with self._lock:
            if self._model is None:
                from fastembed.rerank.cross_encoder import TextCrossEncoder

                self._model = TextCrossEncoder(
                    model_name=self.settings.reranker_model,
                    cache_dir=str(self.settings.data_dir / "cache" / "models"),
                    threads=self.settings.embedding_threads,
                )
            reranked = list(
                self._model.rerank(
                    question,
                    [h.chunk.text for h in hits],
                    batch_size=self.settings.reranker_batch_size,
                )
            )
        output = []
        for index, raw_score in enumerate(reranked):
            hit = hits[index].model_copy(deep=True)
            # A monotone transform makes cross-encoder logits comparable for diversity.
            hit.rerank_score = float(raw_score)
            hit.score = 1 / (1 + math.exp(-max(-50, min(50, float(raw_score)))))
            output.append(hit)
        return sorted(output, key=lambda h: (-h.score, h.chunk.id))

    def close(self) -> None:
        with self._lock:
            self._model = None


class Retriever:
    def __init__(self, store, embedder: Embedder, settings: Settings):
        self.store = store
        self.embedder = embedder
        self.settings = settings
        self.reranker = Reranker(settings)
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def search(
        self,
        query: str,
        filters: SearchFilters | None = None,
        limit: int | None = None,
        mode: str | None = None,
        rerank: bool | None = None,
    ) -> list[SearchHit]:
        filters = filters or SearchFilters()
        limit = limit or self.settings.evidence_limit
        mode = mode or self.settings.retrieval_mode
        rerank = self.settings.reranker_enabled if rerank is None else rerank
        key = fingerprint_json(
            [
                self.store.corpus_revision(),
                self.embedder.fingerprint,
                query,
                filters.model_dump(),
                limit,
                mode,
                rerank,
            ]
        )
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(key)
            if cached and now - cached[0] < self.settings.cache_ttl_seconds:
                self._cache.move_to_end(key)
                return [h.model_copy(deep=True) for h in cached[1]]
        rankings = []
        candidate_limit = max(limit, self.settings.retrieval_limit)
        if mode in ("dense", "hybrid"):
            query_embed = getattr(self.embedder, "embed_query", None)
            vector = query_embed(query) if query_embed else self.embedder.embed([query])[0]
            rankings.append(self.store.query_dense(vector, candidate_limit, filters))
        if mode in ("sparse", "hybrid"):
            sparse = self.embedder.sparse([query], query=True)[0]
            if sparse["indices"]:
                rankings.append(self.store.query_sparse(sparse, candidate_limit, filters))
        hits = reciprocal_rank_fusion(rankings)
        if rerank:
            hits = self.reranker.rerank(query, hits[: self.settings.retrieval_limit])
        hits = diversify(hits, limit)
        with self._lock:
            self._cache[key] = (now, hits)
            while len(self._cache) > 256:
                self._cache.popitem(last=False)
        return [h.model_copy(deep=True) for h in hits]

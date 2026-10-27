from types import SimpleNamespace

import numpy as np

from investigation.config import Settings
from investigation.embeddings import DenseEmbedder, HashEmbedder, lexical_tokens, token_id


def test_dense_document_and_model_specific_query_caches_are_distinct(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path, embedding_dimension=16)
    calls = []

    def generate(texts, query=False, **kwargs):
        calls.append((query, list(texts)))
        for _ in texts:
            vector = np.zeros(16, dtype=np.float32)
            vector[1 if query else 0] = 2
            yield vector

    embedder = DenseEmbedder(settings)
    embedder._model = SimpleNamespace(
        embed=generate, query_embed=lambda texts, **kwargs: generate(texts, query=True)
    )
    try:
        document = embedder.embed(["same text", "same text"])
        query = embedder.embed_query("same text")
        assert document == [[1.0] + [0.0] * 15] * 2
        assert query == [0.0, 1.0] + [0.0] * 14
        assert embedder.embed_query("same text") == query
        assert calls == [(False, ["same text"]), (True, ["same text"])]
    finally:
        embedder.close()
    reopened = DenseEmbedder(settings)
    try:
        assert reopened.embed(["same text"]) == document[:1]
        assert reopened.embed_query("same text") == query
        assert reopened._model is None, "Persistent cache hits must not load an inference model"
    finally:
        reopened.close()


def test_sparse_query_is_not_document_tf_weight_and_indices_are_stable():
    embedder = HashEmbedder(64)
    query = embedder.sparse(["The ATLAS atlas payment"], query=True)[0]
    document = embedder.sparse(["The ATLAS atlas payment"])[0]
    assert query["indices"] == sorted({token_id("atlas"), token_id("payment")})
    assert query["values"] == [1.0, 1.0]
    assert document["values"] != query["values"]
    assert lexical_tokens("The café and თბილისი") == ["café", "თბილისი"]

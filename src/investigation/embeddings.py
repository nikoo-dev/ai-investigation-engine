"""Local ONNX dense embeddings and deterministic BM25 sparse representations.

HashEmbedder is exclusively an offline test double. It does not satisfy semantic search.
"""

import hashlib
import json
import re
import sqlite3
import threading
from collections import Counter
from typing import Any, Protocol

import numpy as np

from investigation.config import Settings

STOPWORDS = frozenset(
    "a an and are as at be been being by for from had has have he her his i in is it its "
    "of on or she that the their them they this to was were will with you your".split()
)


def lexical_tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.casefold()) if t not in STOPWORDS]


def token_id(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode(), digest_size=4).digest(), "little")


class Embedder(Protocol):
    dimension: int
    fingerprint: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def sparse(self, texts: list[str], query: bool = False) -> list[dict]: ...


class SparseMixin:
    avg_length: float = 150.0

    def sparse(self, texts: list[str], query: bool = False) -> list[dict]:
        results: list[dict] = []
        for text in texts:
            counts = Counter(lexical_tokens(text))
            size = sum(counts.values())
            values: dict[int, float] = {}
            for token, count in counts.items():
                index = token_id(token)
                weight = (
                    1.0
                    if query
                    else count * 2.2 / (count + 1.2 * (0.25 + 0.75 * size / self.avg_length))
                )
                # Summing handles the rare 32-bit token-hash collision consistently.
                values[index] = values.get(index, 0.0) + weight
            indices = sorted(values)
            results.append({"indices": indices, "values": [values[i] for i in indices]})
        return results


class HashEmbedder(SparseMixin):
    """Deterministic lexical projection used only by unit/integration test fixtures."""

    def __init__(self, dimension: int = 64, avg_length: float = 150.0):
        self.dimension = dimension
        self.avg_length = avg_length
        self.fingerprint = f"test-hash-v1:{dimension}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            vector = np.zeros(self.dimension, dtype=np.float32)
            for token in lexical_tokens(text):
                index = token_id(token)
                vector[index % self.dimension] += 1 if (index >> 10) % 2 else -1
            norm = float(np.linalg.norm(vector))
            if norm:
                vector /= norm
            results.append(vector.tolist())
        return results


class DenseEmbedder(SparseMixin):
    """Lazy FastEmbed model with a fingerprinted SQLite cache of document/query vectors."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.dimension = settings.embedding_dimension
        self.avg_length = settings.bm25_avg_length
        self.fingerprint = f"fastembed:{settings.embedding_model}:{self.dimension}:v1"
        self._model: Any = None
        self._tokenizer: Any = None
        self._lock = threading.RLock()
        cache_dir = settings.data_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(cache_dir / "embeddings.sqlite3", check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS embeddings (key TEXT PRIMARY KEY, value BLOB)")

    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(
                model_name=self.settings.embedding_model,
                cache_dir=str(self.settings.data_dir / "cache" / "models"),
                threads=self.settings.embedding_threads,
            )
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, query=False)

    def embed_query(self, query: str) -> list[float]:
        return self._embed([query], query=True)[0]

    def _embed(self, texts: list[str], query: bool) -> list[list[float]]:
        if not texts:
            return []
        with self._lock:
            keys = [
                hashlib.sha256(
                    (self.fingerprint + (":query" if query else "") + "\0" + t).encode()
                ).hexdigest()
                for t in texts
            ]
            vectors: dict[str, list[float]] = {}
            for key in set(keys):
                row = self._db.execute(
                    "SELECT value FROM embeddings WHERE key=?", (key,)
                ).fetchone()
                if row:
                    vectors[key] = np.frombuffer(row[0], dtype=np.float32).tolist()
            missing = list(dict.fromkeys(k for k in keys if k not in vectors))
            text_by_key = dict(zip(keys, texts, strict=True))
            if missing:
                model = self._load()
                method = model.query_embed if query else model.embed
                generated = method(
                    [text_by_key[k] for k in missing], batch_size=self.settings.embedding_batch_size
                )
                for key, raw in zip(missing, generated, strict=True):
                    vector = np.asarray(raw, dtype=np.float32)
                    if vector.shape != (self.dimension,):
                        raise ValueError(
                            f"Embedding dimension {vector.shape} does not match configured {self.dimension}"
                        )
                    norm = float(np.linalg.norm(vector))
                    if norm:
                        vector /= norm
                    vectors[key] = vector.tolist()
                    self._db.execute(
                        "INSERT OR REPLACE INTO embeddings VALUES (?,?)", (key, vector.tobytes())
                    )
                self._db.commit()
            return [vectors[k] for k in keys]

    @property
    def max_content_tokens(self) -> int:
        with self._lock:
            original = self._load().model.tokenizer
            truncation = original.truncation or {"max_length": 256}
            return int(truncation["max_length"]) - original.num_special_tokens_to_add(False)

    def token_spans(self, text: str) -> list[tuple[int, int]]:
        """Full original-text offsets, without the model's inference-time truncation.

        The cloned tokenizer is never used for inference; turning off truncation on
        the model itself would change its behavior and introduce a thread race.
        """
        with self._lock:
            if self._tokenizer is None:
                from tokenizers import Tokenizer

                self._tokenizer = Tokenizer.from_str(self._load().model.tokenizer.to_str())
                self._tokenizer.no_truncation()
                self._tokenizer.no_padding()
            return [
                (a, b)
                for a, b in self._tokenizer.encode(text, add_special_tokens=False).offsets
                if b > a
            ]

    def close(self) -> None:
        with self._lock:
            self._db.close()
            self._model = None
            self._tokenizer = None


def make_embedder(settings: Settings) -> Embedder:
    if settings.embedding_backend == "hash":
        return HashEmbedder(settings.embedding_dimension, settings.bm25_avg_length)
    return DenseEmbedder(settings)


def fingerprint_json(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()

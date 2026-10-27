"""Composition root; the web application and CLI share exactly one pipeline."""

from dataclasses import dataclass

from investigation.config import Settings
from investigation.embeddings import Embedder, make_embedder
from investigation.engine import Engine
from investigation.ingestion import Ingestor
from investigation.storage import Store


@dataclass
class Runtime:
    settings: Settings
    store: Store
    embedder: Embedder
    ingestion: Ingestor
    engine: Engine

    def close(self) -> None:
        self.engine.close()
        self.store.close()
        close = getattr(self.embedder, "close", None)
        if close:
            close()


def build_runtime(settings: Settings | None = None) -> Runtime:
    settings = settings or Settings()
    embedder = make_embedder(settings)
    store = Store(settings, embedder.dimension)
    ingestion = Ingestor(store, embedder, settings)
    engine = Engine(settings, store, embedder)
    return Runtime(settings, store, embedder, ingestion, engine)

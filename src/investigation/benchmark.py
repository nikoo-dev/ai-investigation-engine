"""Measured latency/throughput/RSS reports. Runs actual requests; no fabricated scale claims."""

from __future__ import annotations

import json
import math
import platform
import statistics
import threading
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import psutil

from investigation.models import InvestigationRequest, utc_now


class _RSSSampler:
    """Sample independently of request completion; process memory only, not Qdrant server."""

    def __init__(self, interval: float = 0.025):
        self.process = psutil.Process()
        self.interval = interval
        self.start_bytes = self.process.memory_info().rss
        self.peak_bytes = self.start_bytes
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self._stop.wait(self.interval):
            self.peak_bytes = max(self.peak_bytes, self.process.memory_info().rss)

    def __enter__(self) -> _RSSSampler:
        self._thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.peak_bytes = max(self.peak_bytes, self.process.memory_info().rss)
        self._stop.set()
        self._thread.join(timeout=1)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    if not 0 <= fraction <= 1:
        raise ValueError("fraction must be in [0, 1]")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def run_benchmark(
    engine: Any,
    questions: list[str],
    output_dir: Path,
    repeats: int = 1,
    concurrency: int = 1,
    warmup: int = 1,
) -> dict[str, Any]:
    if not questions or repeats < 1 or concurrency < 1 or warmup < 0:
        raise ValueError(
            "Provide questions and positive repeats/concurrency; warmup cannot be negative"
        )
    for question in questions[:warmup]:
        engine.investigate(InvestigationRequest(question=question, use_cache=False))
    start = time.perf_counter()
    rows = []

    def request(question: str) -> dict[str, Any]:
        began = time.perf_counter()
        try:
            answer = engine.investigate(InvestigationRequest(question=question, use_cache=False))
            return {
                "question": question,
                "latency_ms": (time.perf_counter() - began) * 1000,
                "status": answer.status,
                "error": None,
                "usage": answer.usage,
            }
        except Exception as exc:
            return {
                "question": question,
                "latency_ms": (time.perf_counter() - began) * 1000,
                "status": "error",
                "error": type(exc).__name__,
            }

    with _RSSSampler() as memory, ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(request, question) for _ in range(repeats) for question in questions]
        for future in as_completed(futures):
            rows.append(future.result())
    elapsed = time.perf_counter() - start
    latencies = [row["latency_ms"] for row in rows]
    store = getattr(engine, "store", None)
    settings = getattr(engine, "settings", None)
    report = {
        "created_at": utc_now(),
        "kind": "end_to_end_investigation",
        "requests": len(rows),
        "concurrency": concurrency,
        "repeats": repeats,
        "warmup_requests": min(warmup, len(questions)),
        "answer_cache_enabled": False,
        "retrieval_cache_enabled": False,
        "embedding_cache_enabled": True,
        "seconds": elapsed,
        "requests_per_second": len(rows) / elapsed,
        "latency_p50_ms": statistics.median(latencies),
        "latency_p95_ms": percentile(latencies, 0.95),
        "latency_min_ms": min(latencies),
        "latency_max_ms": max(latencies),
        "errors": sum(row["status"] == "error" for row in rows),
        "rss_start_bytes": memory.start_bytes,
        "rss_peak_sampled_bytes": memory.peak_bytes,
        "rss_sampling_interval_ms": memory.interval * 1000,
        "corpus_stats": store.stats() if store else None,
        "corpus_revision": store.corpus_revision() if store else None,
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "llm_provider": getattr(settings, "llm_provider", None),
            "embedding_model": getattr(settings, "embedding_model", None),
        },
        "limitations": [
            "RSS is sampled every 25 ms and can miss shorter transient peaks; external Qdrant-server RSS is not included.",
            "Local/client mode may use exact vector scans. Report server mode separately before extrapolating scale.",
            "A run with fewer than 50,000 stored documents is a small-corpus benchmark, not evidence of 50,000-record performance.",
        ],
        "rows": rows,
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "benchmark.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Performance benchmark",
        "",
        f"Recorded: {report['created_at']}",
        "",
        f"Corpus: `{report['corpus_stats']}`. Provider: `{report['environment']['llm_provider']}`.",
        "",
        f"Requests: {len(rows)} at concurrency {concurrency}; errors: {report['errors']}.",
        "",
        f"p50: {report['latency_p50_ms']:.1f} ms; p95: {report['latency_p95_ms']:.1f} ms; throughput: {report['requests_per_second']:.3f} requests/s.",
        "",
        f"Sampled peak process RSS: {memory.peak_bytes / (1024**2):.1f} MiB.",
        "",
        "Limitations:",
        "",
    ]
    lines.extend(f"- {item}" for item in report["limitations"])
    (output_dir / "benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def run_ingestion_benchmark(
    ingestor: Any,
    records: Iterable[dict[str, Any]],
    output_dir: Path,
    batch_size: int = 64,
) -> dict[str, Any]:
    """Measure a real, resumable import without erasing or altering unrelated records."""
    store = ingestor.store
    before = store.stats()
    start = time.perf_counter()
    with _RSSSampler() as memory:
        counts = ingestor.ingest_records(records, batch_size=batch_size)
    elapsed = time.perf_counter() - start
    after = store.stats()
    report = {
        "created_at": utc_now(),
        "kind": "batch_ingestion",
        "seconds": elapsed,
        "batch_size": batch_size,
        "counts": counts,
        "before": before,
        "after": after,
        "processed_records_per_second": counts.get("processed", 0) / elapsed,
        "created_records_per_second": counts.get("created", 0) / elapsed,
        "active_document_delta": after["documents"] - before["documents"],
        "at_least_50000_active_documents": after["documents"] >= 50000,
        "rss_start_bytes": memory.start_bytes,
        "rss_peak_sampled_bytes": memory.peak_bytes,
        "rss_sampling_interval_ms": memory.interval * 1000,
        "corpus_revision": store.corpus_revision(),
        "embedding_model": ingestor.settings.embedding_model,
        "embedding_backend": ingestor.settings.embedding_backend,
        "chunk_strategy": ingestor.settings.chunk_strategy,
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
        },
        "limitations": [
            "Existing identical records are counted as duplicates, not newly ingested documents.",
            "The after count proves stored active documents, not that every submitted row was indexed; inspect failures and ID reconciliation.",
            "Memory sampling includes this Python process only, not an external vector database.",
        ],
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "ingestion.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "ingestion.md").write_text(
        "# Ingestion benchmark\n\n"
        f"Recorded: {report['created_at']}\n\n"
        f"Before: `{before}`. After: `{after}`.\n\n"
        f"Counts: `{counts}`. Elapsed: {elapsed:.2f} seconds; "
        f"processed throughput: {report['processed_records_per_second']:.2f} records/s.\n\n"
        f"Peak sampled Python RSS: {memory.peak_bytes / (1024**2):.1f} MiB.\n\n"
        + "\n".join(f"- {item}" for item in report["limitations"])
        + "\n",
        encoding="utf-8",
    )
    return report

"""Reproducible ablations on one attributed corpus and one held-out case manifest.

Index construction is deliberately separate from inference: changing the chunker
or embedding model creates a distinct compatible index, while retrieval/reranker
ablations reuse that exact index. No run touches the application's main database.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import logging
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from investigation.config import Settings
from investigation.datasets import file_sha256, read_jsonl
from investigation.embeddings import make_embedder
from investigation.engine import Engine
from investigation.evaluation import EvaluationCase, compare_reports, evaluate, load_cases
from investigation.ingestion import Ingestor
from investigation.models import utc_now
from investigation.retrieval import Reranker
from investigation.runtime import Runtime
from investigation.storage import Store

logger = logging.getLogger(__name__)
DEFAULT_INDEX_ROOT = Path(".cache/experiments/indexes")


@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    chunk_strategy: Literal["fixed", "structure"] = "structure"
    retrieval_mode: Literal["dense", "hybrid"] = "hybrid"
    reranker_enabled: bool = True
    contrast: str = "baseline"


def experiment_configs(include_alternative_model: bool = True) -> list[ExperimentConfig]:
    """One-factor-at-a-time ablations rather than an unexplained mixed comparison."""
    configs = [
        ExperimentConfig(name="minilm-structure-hybrid-rerank"),
        ExperimentConfig(
            name="minilm-fixed-hybrid-rerank", chunk_strategy="fixed", contrast="chunking"
        ),
        ExperimentConfig(
            name="minilm-structure-dense-rerank", retrieval_mode="dense", contrast="hybrid-search"
        ),
        ExperimentConfig(
            name="minilm-structure-hybrid-no-rerank", reranker_enabled=False, contrast="reranking"
        ),
    ]
    if include_alternative_model:
        configs.append(
            ExperimentConfig(
                name="bge-small-structure-hybrid-rerank",
                embedding_model="BAAI/bge-small-en-v1.5",
                contrast="embedding-model",
            )
        )
    return configs


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def select_experiment_records(
    corpus_path: Path,
    cases: list[EvaluationCase],
    minimum_records: int = 1000,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Retain every gold source, then add smallest SHA256(seed:id) distractors.

    The heap bounds retained passage bodies to the requested subset size plus gold
    sources. Input order cannot affect selected IDs. Exact input and selected-record
    hashes are both recorded because they establish different reproducibility facts.
    """
    if minimum_records < 1:
        raise ValueError("minimum_records must be positive")
    if not cases:
        raise ValueError("At least one evaluation case is required")
    required = {doc_id for case in cases for doc_id in case.gold_document_ids}
    forced: dict[str, dict[str, Any]] = {}
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    seen: dict[str, str] = {}
    for row in read_jsonl(Path(corpus_path)):
        identity = row.get("id")
        if not isinstance(identity, str) or not identity:
            raise ValueError("Every experiment source requires a nonempty string id")
        if not isinstance(row.get("text"), str) or not row["text"].strip():
            raise ValueError(f"Source {identity} has no text")
        digest = _canonical_hash(row)
        if identity in seen:
            if seen[identity] != digest:
                raise ValueError(f"Source ID {identity} occurs with conflicting records")
            continue
        seen[identity] = digest
        if identity in required:
            forced[identity] = row
            continue
        score = int(hashlib.sha256(f"{seed}:{identity}".encode()).hexdigest(), 16)
        item = (-score, identity, row)
        if len(candidates) < minimum_records:
            heapq.heappush(candidates, item)
        elif score < -candidates[0][0]:
            heapq.heapreplace(candidates, item)
    missing = required - forced.keys()
    if missing:
        raise ValueError(f"Corpus is missing {len(missing)} gold sources: {sorted(missing)[:5]}")
    if len(seen) < minimum_records:
        raise ValueError(f"Corpus has {len(seen)} unique source IDs; need {minimum_records}")
    needed = max(0, minimum_records - len(forced))
    chosen = sorted(candidates, key=lambda item: (-item[0], item[1]))[:needed]
    records = sorted([*forced.values(), *(item[2] for item in chosen)], key=lambda row: row["id"])
    manifest = {
        "version": 1,
        "seed": seed,
        "selection": "Every gold source ID from test/security cases, then ascending SHA256(seed:id) distractors; records sorted by ID.",
        "minimum_records": minimum_records,
        "source_unique_ids": len(seen),
        "selected_records": len(records),
        "forced_gold_sources": len(forced),
        "distractor_sources": len(chosen),
        "selected_ids": [row["id"] for row in records],
        "gold_ids": sorted(required),
        "selected_records_sha256": _canonical_hash(records),
        "source_corpus_sha256": file_sha256(Path(corpus_path)),
        "dataset_counts": dict(
            Counter(str(row.get("metadata", {}).get("dataset", "unknown")) for row in records)
        ),
    }
    return records, manifest


def _build_experiment_runtime(settings: Settings, cache_settings: Settings) -> Runtime:
    """Share only immutable model files/vector caches, never the main Qdrant path."""
    embedder = make_embedder(cache_settings)
    try:
        store = Store(settings, embedder.dimension)
    except Exception:
        close = getattr(embedder, "close", None)
        if close:
            close()
        raise
    try:
        ingestion = Ingestor(store, embedder, settings)
        engine = Engine(settings, store, embedder)
        engine.retriever.reranker = Reranker(cache_settings)
        return Runtime(settings, store, embedder, ingestion, engine)
    except Exception:
        store.close()
        close = getattr(embedder, "close", None)
        if close:
            close()
        raise


def _usage_summary(report: dict[str, Any]) -> dict[str, Any]:
    totals: dict[str, float] = {}
    providers: Counter = Counter()
    models: Counter = Counter()
    for row in report.get("rows", []):
        answer = row.get("answer") or {}
        providers[str(answer.get("provider", "unavailable"))] += 1
        models[str(answer.get("model", "unavailable"))] += 1
        for key, value in answer.get("usage", {}).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[key] = totals.get(key, 0.0) + value
    return {
        "actual_providers": dict(providers),
        "actual_models": dict(models),
        "usage_totals": totals,
    }


def _write_summary(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_experiments(
    settings: Settings,
    corpus_path: Path,
    cases_path: Path,
    output_dir: Path,
    minimum_records: int = 1000,
    include_alternative_model: bool = True,
    seed: int = 42,
    index_root: Path | None = None,
) -> dict[str, Any]:
    """Measure five configurations; retain complete predictions and exact provenance.

    Tests may inject a fake runtime, but ordinary calls refuse hash embeddings.
    Extractive answers are allowed for retrieval experiments and explicitly labeled;
    they must not be presented as evidence of real LLM performance.
    """
    if settings.embedding_backend != "fastembed":
        raise ValueError(
            "Semantic experiments require EMBEDDING_BACKEND=fastembed; hash fixtures are not semantic results"
        )
    corpus_path, cases_path, output_dir = Path(corpus_path), Path(cases_path), Path(output_dir)
    cases = [case for case in load_cases(cases_path) if case.split in {"test", "security"}]
    if not cases:
        raise ValueError("Experiment manifest has no test or security cases")
    records, selection = select_experiment_records(corpus_path, cases, minimum_records, seed)
    configs = experiment_configs(include_alternative_model)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_summary(output_dir / "selection.json", selection)
    evaluation_digest = hashlib.sha256(
        "\n".join(case.model_dump_json() for case in cases).encode()
    ).hexdigest()
    result: dict[str, Any] = {
        "version": 1,
        "status": "running",
        "created_at": utc_now(),
        "selection": {
            key: value
            for key, value in selection.items()
            if key not in {"selected_ids", "gold_ids"}
        },
        "case_manifest_sha256": file_sha256(cases_path),
        "evaluation_sha256": evaluation_digest,
        "case_ids": [case.id for case in cases],
        "case_count": len(cases),
        "split_counts": dict(Counter(case.split for case in cases)),
        "requested_llm_provider": settings.llm_provider,
        "requested_llm_model": settings.llm_model,
        "comparison_design": "One factor differs from the first configuration in each ablation.",
        "configurations": [],
        "limitations": [
            "This controlled subset ablation does not replace the separate >=50,000-record ingestion and load test.",
            "Gold source inclusion is guaranteed, not gold ranking. Only source passages are indexed; questions and reference answers remain outside searchable text.",
            "Test and security cases are reported separately in each report; tuning cases are excluded.",
            "Repeated configurations share embedding caches and compatible indexes; latency includes per-engine lazy reranker/model initialization and is not a clean cold-start benchmark.",
            "Extractive-provider answers measure an evidence-only fallback, not LLM reasoning. Actual providers/models and usage totals are reported per configuration.",
            "Token F1 and source-label citation metrics are proxies; inspect per-case predictions and claim entailment before claiming semantic correctness.",
        ],
    }
    summary_path = output_dir / "summary.json"
    _write_summary(summary_path, result)
    began = time.perf_counter()
    completed_report_paths: list[Path] = []
    for config in configs:
        options = {
            "embedding_model": config.embedding_model,
            "embedding_dimension": config.embedding_dimension,
            "chunk_strategy": config.chunk_strategy,
            "chunk_tokens": settings.chunk_tokens,
            "chunk_overlap": settings.chunk_overlap,
            "bm25_avg_length": settings.bm25_avg_length,
            "corpus": selection["selected_records_sha256"],
            "pipeline": "model-token-offsets-title-prefix-v2",
        }
        identity = _canonical_hash(options)[:20]
        directory = Path(index_root or DEFAULT_INDEX_ROOT) / identity
        variant = settings.model_copy(
            update={
                "environment": "local",
                "data_dir": directory,
                "qdrant_url": None,
                "qdrant_api_key": None,
                "collection_prefix": f"experiment_{identity}",
                "embedding_backend": "fastembed",
                "embedding_model": config.embedding_model,
                "embedding_dimension": config.embedding_dimension,
                "chunk_strategy": config.chunk_strategy,
                "retrieval_mode": config.retrieval_mode,
                "reranker_enabled": config.reranker_enabled,
                "cache_ttl_seconds": 0,
            }
        )
        cache_settings = variant.model_copy(update={"data_dir": settings.data_dir})
        runtime: Runtime | None = None
        logger.info("Experiment %s: %d records, %d cases", config.name, len(records), len(cases))
        stage_began = time.perf_counter()
        try:
            runtime = _build_experiment_runtime(variant, cache_settings)
            if not runtime.embedder.fingerprint.startswith("fastembed:"):
                raise ValueError("Runtime did not load a semantic embedding provider")
            ingestion = runtime.ingestion.ingest_records(
                records, batch_size=settings.embedding_batch_size
            )
            stats = runtime.store.stats()
            if ingestion.get("failed", 0) or stats["documents"] != len(records):
                raise ValueError(
                    "Indexed independent record count differs from the fixed experiment corpus; inspect duplicate IDs/text and ingestion failures"
                )
            ingestion_seconds = time.perf_counter() - stage_began
            report_path = output_dir / config.name
            report = evaluate(runtime.engine, cases, report_path, config.name)
            if report["evaluation_sha256"] != evaluation_digest:
                raise ValueError("Evaluation manifest changed during the experiment")
            row = {
                "configuration": asdict(config),
                "status": "completed_with_errors"
                if report["aggregate"].get("error_rate", 0)
                else "complete",
                "actual_embedding_fingerprint": runtime.embedder.fingerprint,
                "index_identity": identity,
                "index_path": str(directory),
                "ingestion_counts": ingestion,
                "ingestion_seconds": ingestion_seconds,
                "corpus_stats": stats,
                "aggregate": report["aggregate"],
                "by_source": report.get("by_source", {}),
                "by_split": report.get("by_split", {}),
                "report": str((Path(config.name) / "results.json").as_posix()),
                **_usage_summary(report),
            }
            result["configurations"].append(row)
            completed_report_paths.append(report_path / "results.json")
            _write_summary(summary_path, result)
        except Exception as exc:
            result["status"] = "failed"
            result["failed_configuration"] = config.name
            result["error_type"] = type(exc).__name__
            result["duration_seconds"] = time.perf_counter() - began
            _write_summary(summary_path, result)
            raise
        finally:
            if runtime:
                runtime.close()
    compare_reports(completed_report_paths, output_dir / "comparison.md")
    result["status"] = "complete"
    result["duration_seconds"] = time.perf_counter() - began
    _write_summary(summary_path, result)
    (output_dir / "summary.md").write_text(render_experiment_summary(result), encoding="utf-8")
    return result


def render_experiment_summary(report: dict[str, Any]) -> str:
    lines = [
        "# Controlled retrieval and chunking experiments",
        "",
        f"Generated: {report['created_at']}. Status: {report['status']}.",
        "",
        f"Each configuration uses **{report['selection']['selected_records']} identical source records** and **{report['case_count']} identical cases**. Split counts: `{report['split_counts']}`.",
        "",
        f"Selected corpus SHA-256: `{report['selection']['selected_records_sha256']}`. Evaluation SHA-256: `{report['evaluation_sha256']}`.",
        "",
        "The first row is the baseline. Every other row changes one factor only. Scores include failure cases in their applicable denominators.",
        "",
        "Configuration | Contrast | Recall@10 | All-support@10 | MRR | Token F1 | Citation validity | Error rate | p95 ms",
        "--- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---:",
    ]
    for row in report["configurations"]:
        aggregate = row["aggregate"]
        cells = [row["configuration"]["name"], row["configuration"]["contrast"]]
        cells += [
            f"{aggregate[key]:.4f}" if key in aggregate else "n/a"
            for key in [
                "recall_at_10",
                "all_support_at_10",
                "mrr",
                "answer_token_f1",
                "citation_source_validity",
                "error_rate",
                "latency_p95_ms",
            ]
        ]
        lines.append(" | ".join(cells))
    lines.extend(["", "## Actual model execution", ""])
    for row in report["configurations"]:
        lines.append(
            f"- `{row['configuration']['name']}`: embedding `{row['actual_embedding_fingerprint']}`; providers `{row['actual_providers']}`; models `{row['actual_models']}`; usage totals `{row['usage_totals']}`."
        )
    lines.extend(["", "## Interpretation", ""])
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    lines.extend(
        [
            "",
            "Read the per-configuration reports for source/split breakdowns and failure analysis. The complete selected IDs are in `selection.json`; unedited per-case answers, citations and traces are retained in each `results.json`.",
            "",
        ]
    )
    return "\n".join(lines)

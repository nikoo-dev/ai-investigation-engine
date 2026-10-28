"""Transparent evaluation: retrieval labels, exact citations and bounded answer proxies.

Scores deliberately do not equate lexical answer overlap to semantic correctness.
Per-case outputs and limitations are preserved for independent manual review.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, model_validator

from investigation.evaluation_checkpoint import (
    EvaluationCheckpoint,
    atomic_json,
    software_fingerprint,
)
from investigation.models import (
    InvestigationAnswer,
    InvestigationPlan,
    InvestigationRequest,
    utc_now,
)


class EvaluationCase(BaseModel):
    id: str
    category: Literal[
        "direct", "comparison", "multi_hop", "unanswerable", "contradictory", "prompt_injection"
    ]
    question: str = Field(min_length=3)
    expected_answers: list[str] = []
    required_facts: list[list[str]] = []
    gold_document_ids: list[str] = []
    gold_passage_ids: list[str] = []
    expected_status: Literal[
        "answered", "insufficient_evidence", "conflicting_evidence", "any_safe"
    ] = "answered"
    required_hops: int = Field(default=1, ge=1)
    split: Literal["tuning", "test", "security"] = "test"
    source: str = "authored-incidents"
    forbidden_output_patterns: list[str] = []
    forbidden_exact_answers: list[str] = []
    notes: str = ""

    @model_validator(mode="after")
    def validate_case(self) -> EvaluationCase:
        if (
            self.expected_status in {"answered", "conflicting_evidence"}
            and not self.gold_document_ids
        ):
            raise ValueError("Answerable cases require gold source-document labels")
        if self.expected_status == "answered" and not self.expected_answers:
            raise ValueError("Answerable cases require at least one reference answer")
        return self


class InvestigationEngine(Protocol):
    def investigate(self, request: InvestigationRequest) -> InvestigationAnswer: ...


def normalize_answer(text: str) -> str:
    text = text.casefold()
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def token_f1(prediction: str, reference: str) -> float:
    predicted = normalize_answer(prediction).split()
    expected = normalize_answer(reference).split()
    if not predicted or not expected:
        return float(predicted == expected)
    common = sum((Counter(predicted) & Counter(expected)).values())
    if not common:
        return 0.0
    precision, recall = common / len(predicted), common / len(expected)
    return 2 * precision * recall / (precision + recall)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def retrieval_metrics(
    ranked_document_ids: list[str], gold_document_ids: list[str]
) -> dict[str, float | None]:
    gold = set(gold_document_ids)
    if not gold:
        return {
            "recall_at_5": None,
            "recall_at_10": None,
            "mrr": None,
            "all_support_at_10": None,
            "evidence_precision_at_10": None,
        }
    ranked = _unique(ranked_document_ids)
    first_rank = next((i for i, doc_id in enumerate(ranked, 1) if doc_id in gold), None)
    top = set(ranked[:10])
    return {
        "recall_at_5": len(set(ranked[:5]) & gold) / len(gold),
        "recall_at_10": len(top & gold) / len(gold),
        "mrr": 1 / first_rank if first_rank else 0.0,
        "all_support_at_10": float(gold <= top),
        "evidence_precision_at_10": len(top & gold) / len(top) if top else 0.0,
    }


def score_case(
    case: EvaluationCase, answer: InvestigationAnswer, store: Any = None
) -> dict[str, float | None]:
    metrics = retrieval_metrics(answer.retrieved_document_ids, case.gold_document_ids)
    applicable = case.expected_status in {"answered", "conflicting_evidence"}
    predicted_text = re.sub(r"\[[^\]]+\]", " ", answer.answer)
    metrics["answer_token_f1"] = (
        max((token_f1(predicted_text, ref) for ref in case.expected_answers), default=0.0)
        if applicable
        else None
    )
    metrics["answer_exact_match"] = (
        float(
            any(
                normalize_answer(predicted_text) == normalize_answer(ref)
                for ref in case.expected_answers
            )
        )
        if applicable
        else None
    )
    if applicable and not predicted_text.strip():
        metrics["answer_token_f1"] = 0.0
        metrics["answer_exact_match"] = 0.0
    normalized_prediction = normalize_answer(predicted_text)

    def contains_fact(aliases: list[str]) -> bool:
        return any(
            re.search(
                r"(?<!\w)" + re.escape(normalize_answer(alias)) + r"(?!\w)", normalized_prediction
            )
            is not None
            for alias in aliases
        )

    metrics["answer_fact_recall"] = (
        sum(contains_fact(aliases) for aliases in case.required_facts) / len(case.required_facts)
        if case.required_facts
        else None
    )
    metrics["status_accuracy"] = (
        float(answer.status == case.expected_status) if case.expected_status != "any_safe" else None
    )
    metrics["abstention_accuracy"] = (
        float(answer.status == "insufficient_evidence")
        if case.expected_status == "insufficient_evidence"
        else None
    )
    metrics["contradiction_accuracy"] = (
        float(answer.status == "conflicting_evidence" and bool(answer.conflicts))
        if case.expected_status == "conflicting_evidence"
        else None
    )
    gold = set(case.gold_document_ids)
    cited = {citation.document_id for citation in answer.citations}
    metrics["citation_gold_precision"] = (
        sum(c.document_id in gold for c in answer.citations) / len(answer.citations)
        if answer.citations and gold
        else (0.0 if gold else None)
    )
    metrics["citation_gold_recall"] = len(cited & gold) / len(gold) if gold else None
    valid_citations = None
    if store is not None:
        chunks = {
            chunk.id: chunk for chunk in store.get_chunks([c.passage_id for c in answer.citations])
        }
        valid_citations = (
            sum(
                citation.passage_id in chunks
                and chunks[citation.passage_id].document_id == citation.document_id
                and chunks[citation.passage_id].revision == citation.revision
                and bool(citation.quote.strip())
                and citation.quote in chunks[citation.passage_id].text
                for citation in answer.citations
            )
            / len(answer.citations)
            if answer.citations
            else (0.0 if gold else None)
        )
    metrics["citation_source_validity"] = valid_citations
    citation_ids = {citation.id for citation in answer.citations}
    linked = [identifier for claim in answer.claims for identifier in claim.citation_ids]
    metrics["claim_citation_id_validity"] = (
        sum(identifier in citation_ids for identifier in linked) / len(linked)
        if linked
        else (0.0 if answer.claims else None)
    )
    metrics["claim_citation_coverage"] = (
        sum(bool(claim.citation_ids) for claim in answer.claims) / len(answer.claims)
        if answer.claims
        else None
    )
    if case.category == "prompt_injection":
        output = answer.answer.strip()
        violation = any(
            re.search(pattern, output, re.I) for pattern in case.forbidden_output_patterns
        )
        violation = violation or any(
            output == forbidden for forbidden in case.forbidden_exact_answers
        )
        metrics["injection_output_safety"] = float(not violation)
    else:
        metrics["injection_output_safety"] = None
    metrics["error_rate"] = float(answer.status == "error")
    metrics["elapsed_ms"] = answer.elapsed_ms
    return metrics


def load_cases(path: Path) -> list[EvaluationCase]:
    cases = []
    with Path(path).open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    cases.append(EvaluationCase.model_validate_json(line))
                except ValueError as exc:
                    raise ValueError(f"Invalid evaluation case at {path}:{number}: {exc}") from exc
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation case IDs must be unique")
    if not cases:
        raise ValueError("Evaluation set is empty")
    return cases


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        for key, value in row["metrics"].items():
            if value is not None:
                values[key].append(float(value))
    aggregate: dict[str, Any] = {key: statistics.fmean(items) for key, items in values.items()}
    aggregate["sample_counts"] = {key: len(items) for key, items in values.items()}
    durations = sorted(values.get("elapsed_ms", []))
    if durations:
        aggregate["latency_p50_ms"] = statistics.median(durations)
        aggregate["latency_p95_ms"] = durations[max(0, math.ceil(len(durations) * 0.95) - 1)]
    return aggregate


def evaluate(
    engine: InvestigationEngine,
    cases: list[EvaluationCase],
    output_dir: Path,
    config_name: str = "default",
    request_overrides: dict[str, Any] | None = None,
    *,
    resume: bool = False,
    max_new_cases: int | None = None,
    stop_on_error: bool = False,
) -> dict[str, Any]:
    if not cases:
        raise ValueError("Cannot evaluate an empty case set")
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Evaluation case IDs must be unique")
    if max_new_cases is not None and max_new_cases < 1:
        raise ValueError("max_new_cases must be positive")
    output_dir = Path(output_dir)
    if (output_dir / "results.json").exists() and not (output_dir / "checkpoint.json").exists():
        raise ValueError(
            "Existing results have no resumable checkpoint. Use a new output directory."
        )
    store = getattr(engine, "store", None)
    settings = getattr(engine, "settings", None)
    settings_snapshot = {}
    if settings is not None:
        safe_fields = [
            "embedding_backend",
            "embedding_model",
            "embedding_dimension",
            "chunk_strategy",
            "chunk_tokens",
            "chunk_overlap",
            "bm25_avg_length",
            "retrieval_limit",
            "evidence_limit",
            "retrieval_mode",
            "reranker_enabled",
            "reranker_model",
            "llm_provider",
            "llm_model",
            "min_dense_score",
            "max_tool_calls",
            "max_subquestions",
            "max_context_chars",
        ]
        settings_snapshot = {key: getattr(settings, key, None) for key in safe_fields}
    payload = "\n".join(case.model_dump_json() for case in cases)
    identity = {
        "configuration": config_name,
        "evaluation_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "settings": settings_snapshot,
        "request_overrides": request_overrides or {},
        "corpus_revision": store.corpus_revision() if store else None,
        "corpus_stats": store.stats() if store else None,
        "embedding_fingerprint": getattr(getattr(engine, "embedder", None), "fingerprint", None),
        "software_fingerprint": software_fingerprint(),
    }
    checkpoint = EvaluationCheckpoint(
        output_dir / "checkpoint.json", identity, [case.model_dump() for case in cases], resume
    )
    rows = checkpoint.rows
    started = time.perf_counter()
    checkpoint.save(checkpoint.elapsed_seconds)
    try:
        pending = cases[len(rows) :]
        if max_new_cases is not None:
            pending = pending[:max_new_cases]
        for case in pending:
            case_started = time.perf_counter()
            row: dict[str, Any]
            try:
                request = InvestigationRequest(
                    **{**(request_overrides or {}), "question": case.question, "use_cache": False}
                )
                answer = engine.investigate(request)
                row = {
                    "case": case.model_dump(),
                    "answer": answer.model_dump(),
                    "metrics": score_case(case, answer, store),
                }
            except Exception as exc:  # Failed cases remain in every appropriate denominator.
                failed_answer = InvestigationAnswer(
                    question=case.question,
                    status="error",
                    answer="",
                    plan=InvestigationPlan(subquestions=[case.question]),
                    model="unavailable",
                    provider="unavailable",
                    corpus_revision="unavailable",
                    elapsed_ms=(time.perf_counter() - case_started) * 1000,
                )
                # A failing database must not erase the provider/runtime failure
                # by failing a second time while resolving an empty citation set.
                baseline = score_case(case, failed_answer)
                if store is not None and case.gold_document_ids:
                    baseline["citation_source_validity"] = 0.0
                if case.category == "prompt_injection":
                    baseline["injection_output_safety"] = 0.0
                row = {
                    "case": case.model_dump(),
                    "answer": None,
                    "error": type(exc).__name__,
                    "metrics": baseline,
                }
            rows.append(row)
            checkpoint.save(checkpoint.elapsed_seconds + time.perf_counter() - started)
            if store is not None:
                try:
                    changed = store.corpus_revision() != identity["corpus_revision"]
                except Exception:
                    checkpoint.invalidated = True
                    raise
                if changed:
                    checkpoint.invalidated = True
                    raise ValueError(
                        "Corpus changed during evaluation; use a new run on a stable corpus."
                    )
            if stop_on_error and row["metrics"].get("error_rate"):
                break
    finally:
        # Includes Ctrl+C: only completed attempts are retained. An interrupted
        # in-flight call is attempted again on resume and may have consumed quota.
        duration = checkpoint.elapsed_seconds + time.perf_counter() - started
        checkpoint.save(duration)
        report = _evaluation_report(
            cases,
            rows,
            identity,
            checkpoint,
            duration,
            {
                "llm_min_request_interval_seconds": getattr(
                    settings, "llm_min_request_interval_seconds", 0
                ),
                "max_new_cases": max_new_cases,
                "stop_on_error": stop_on_error,
            },
        )
        atomic_json(output_dir / "results.json", report)
        (output_dir / "report.md").write_text(render_report(report), encoding="utf-8")
    return report


def _evaluation_report(
    cases: list[EvaluationCase],
    rows: list[dict],
    identity: dict,
    checkpoint: EvaluationCheckpoint,
    duration: float,
    run_policy: dict,
) -> dict[str, Any]:
    status = (
        "invalidated"
        if checkpoint.invalidated
        else "complete"
        if len(rows) == len(cases)
        else "partial"
    )
    observed = [EvaluationCase.model_validate(row["case"]) for row in rows]
    report = {
        **identity,
        "status": status,
        "run_id": checkpoint.run_id,
        "created_at": checkpoint.created_at,
        "updated_at": utc_now(),
        "case_count": len(rows),
        "planned_case_count": len(cases),
        "duration_seconds": duration,
        "latest_session_policy": run_policy,
        "aggregate": _aggregate(rows),
        "by_category": {
            category: _aggregate([row for row in rows if row["case"]["category"] == category])
            for category in sorted({case.category for case in observed})
        },
        "by_split": {
            split: _aggregate([row for row in rows if row["case"]["split"] == split])
            for split in sorted({case.split for case in observed})
        },
        "by_source": {
            source: _aggregate([row for row in rows if row["case"]["source"] == source])
            for source in sorted({case.source for case in observed})
        },
        "rows": rows,
        "limitations": [
            "Token F1/exact match and required-fact recall are lexical diagnostics, not proof of semantic correctness.",
            "Citation gold precision checks relevance against source-document labels; source validity checks exact quote, document and revision. Neither proves claim-level entailment.",
            "Prompt-injection output checks catch specific probes only; mutation side effects and secret leakage require the separate integration tests.",
            "The authored incident set is a controlled robustness fixture; HotpotQA held-out questions measure a different, open-domain task. Report them separately.",
            "An extractive/hash test run does not satisfy the real LLM/semantic-search requirement. Provider and embedding configuration are recorded above.",
            "Partial runs are not final evidence. Resume requires identical cases, behavior settings, software and corpus; previous failures are retained and never silently retried.",
            "Session pacing and batch size can change on resume. Cumulative active duration includes pacing and checkpoint writes, not time between sessions. Only the latest session policy is shown.",
        ],
    }
    return report


def render_report(report: dict[str, Any]) -> str:
    lines = [
        f"# Evaluation: {report['configuration']}",
        "",
        f"Generated: {report['created_at']}",
        "",
        f"Run status: {report.get('status', 'complete')}; {report['case_count']} / {report.get('planned_case_count', report['case_count'])} planned cases recorded.",
        "",
        f"Cases: {report['case_count']}. Corpus: `{report.get('corpus_stats')}`.",
        "",
        f"Evaluation SHA-256: `{report['evaluation_sha256']}`.",
        "",
        "## Configuration",
        "",
        "```json",
        json.dumps(report["settings"], indent=2),
        "```",
        "",
        "## Quantitative results",
        "",
        "Metric | Mean | Applicable cases",
        "--- | ---: | ---:",
    ]
    counts = report["aggregate"].get("sample_counts", {})
    for key, value in report["aggregate"].items():
        if isinstance(value, (int, float)):
            lines.append(f"{key} | {value:.4f} | {counts.get(key, '-')}")
    lines.extend(
        [
            "",
            "## Results by question category",
            "",
            "Category | Cases | Recall@10 | All-support@10 | Status accuracy | Answer token F1",
            "--- | ---: | ---: | ---: | ---: | ---:",
        ]
    )
    for category, aggregate in report["by_category"].items():
        count = sum(row["case"]["category"] == category for row in report["rows"])
        metric = lambda key, a=aggregate: f"{a[key]:.3f}" if key in a else "n/a"  # noqa: E731
        lines.append(
            f"{category} | {count} | {metric('recall_at_10')} | {metric('all_support_at_10')} | {metric('status_accuracy')} | {metric('answer_token_f1')}"
        )
    lines.extend(["", "## Corpus-source separation", ""])
    for source, aggregate in report.get("by_source", {}).items():
        count = sum(row["case"]["source"] == source for row in report["rows"])
        lines.append(
            f"- `{source}`: {count} cases; Recall@10 {aggregate.get('recall_at_10', 0):.4f}; "
            f"all-support@10 {aggregate.get('all_support_at_10', 0):.4f}; "
            f"token F1 {aggregate.get('answer_token_f1', 0):.4f}."
        )
    lines.extend(["", "## Split isolation", ""])
    for split, aggregate in report.get("by_split", {}).items():
        count = sum(row["case"]["split"] == split for row in report["rows"])
        lines.append(
            f"- `{split}`: {count} cases; status accuracy {aggregate.get('status_accuracy', 0):.4f}."
        )
    lines.append(
        "Do not report tuning-set scores as held-out results. The aggregate above includes only the cases passed to this run; use the test split for the submission's final quality claim."
    )
    lines.extend(["", "## Failure analysis", ""])
    failures = [
        row
        for row in report["rows"]
        if row["metrics"].get("error_rate", 0) > 0
        or row["metrics"].get("status_accuracy", 1) == 0
        or (
            row["metrics"].get("all_support_at_10") is not None
            and row["metrics"]["all_support_at_10"] < 1
        )
        or (
            row["metrics"].get("answer_fact_recall") is not None
            and row["metrics"]["answer_fact_recall"] < 1
        )
    ]
    for row in failures[:20]:
        case, metrics = row["case"], row["metrics"]
        if row.get("error"):
            reason = "Runtime/provider failure; inspect the saved case error and retry under the same configuration."
        elif metrics.get("all_support_at_10") == 0:
            reason = "At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation."
        elif metrics.get("status_accuracy") == 0:
            reason = "The expected answer/abstention/conflict decision did not match. Inspect evidence coverage and conflicting claims; tune thresholds only on a separate tuning split."
        else:
            reason = "The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation."
        lines.extend(
            [
                f"- `{case['id']}` ({case['category']}): {case['question']}",
                f"  - {reason}",
                f"  - Metrics: `{metrics}`",
            ]
        )
    if not failures:
        lines.append(
            "No failures under these automated checks. Manual entailment and adversarial review remain necessary."
        )
    lines.extend(["", "## Interpretation and limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend(
        [
            "",
            "Full predictions, labels, citations and traces are in `results.json`. No predictions were edited after generation.",
            "",
        ]
    )
    return "\n".join(lines)


def compare_reports(paths: list[Path], output_path: Path) -> str:
    reports = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
    if not reports:
        raise ValueError("At least one report is required")
    if any(
        report.get("status", "complete") != "complete"
        or report.get("planned_case_count", report["case_count"]) != report["case_count"]
        for report in reports
    ):
        raise ValueError("Complete every planned case before comparing evaluation reports")
    if len({report["evaluation_sha256"] for report in reports}) != 1:
        raise ValueError("Configurations must use the identical evaluation manifest")
    lines = [
        "# Configuration comparison",
        "",
        "All configurations use the same evaluation manifest. "
        "Different chunk/model experiments require separate compatible indexes; never mix vectors from different models.",
        "",
        "Configuration | Recall@10 | All-support@10 | MRR | Token F1 | Citation gold precision | Status | p95 ms",
        "--- | ---: | ---: | ---: | ---: | ---: | ---: | ---:",
    ]
    for report in reports:
        values = report["aggregate"]
        cells = [report["configuration"]] + [
            f"{values[key]:.4f}" if key in values else "n/a"
            for key in [
                "recall_at_10",
                "all_support_at_10",
                "mrr",
                "answer_token_f1",
                "citation_gold_precision",
                "status_accuracy",
                "latency_p95_ms",
            ]
        ]
        lines.append(" | ".join(cells))
    lines.extend(
        [
            "",
            "Compare quality with latency and resource cost. Do not select a winner solely on a metric whose applicable case count is small. See each configuration's per-category and failure analysis before making a deployment choice.",
            "",
        ]
    )
    rendered = "\n".join(lines)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(rendered, encoding="utf-8")
    return rendered

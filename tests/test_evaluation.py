from types import SimpleNamespace

import pytest

from investigation.benchmark import percentile, run_benchmark, run_ingestion_benchmark
from investigation.evaluation import (
    EvaluationCase,
    compare_reports,
    evaluate,
    load_cases,
    normalize_answer,
    retrieval_metrics,
    score_case,
    token_f1,
)
from investigation.models import (
    Chunk,
    Citation,
    Claim,
    Conflict,
    InvestigationAnswer,
    InvestigationPlan,
    SourceLocation,
)


def case(**overrides):
    return EvaluationCase(
        **{
            "id": "one",
            "category": "direct",
            "question": "Where was the service running?",
            "expected_answers": ["Tbilisi"],
            "required_facts": [["Tbilisi"]],
            "gold_document_ids": ["doc1"],
            **overrides,
        }
    )


def answer(**overrides):
    return InvestigationAnswer(
        **{
            "question": "Where was the service running?",
            "status": "answered",
            "answer": "Tbilisi",
            "plan": InvestigationPlan(subquestions=["Where was the service running?"]),
            "model": "test",
            "provider": "extractive",
            "corpus_revision": "r1",
            "retrieved_document_ids": ["doc1"],
            **overrides,
        }
    )


def test_retrieval_uses_unique_document_ranks_and_all_support():
    result = retrieval_metrics(["x", "x", "a", "b"], ["a", "b"])
    assert result["recall_at_5"] == 1
    assert result["mrr"] == 0.5
    assert result["all_support_at_10"] == 1
    assert result["evidence_precision_at_10"] == 2 / 3
    assert retrieval_metrics([], ["a"])["mrr"] == 0
    assert retrieval_metrics(["x"], [])["mrr"] is None


def test_answer_normalization_and_token_f1_do_not_claim_semantic_judgment():
    assert normalize_answer("The GATEWAY, a service!") == "gateway service"
    assert token_f1("the Orion team", "Orion") == pytest.approx(2 / 3)
    assert token_f1("", "") == 1
    assert token_f1("a city", "a person") == 0


def test_citations_are_resolved_against_exact_passage_document_revision_and_quote():
    chunk = Chunk(
        id="p1",
        document_id="doc1",
        revision=1,
        title="Source",
        text="Runs in Tbilisi.",
        checksum="x",
    )
    store = SimpleNamespace(get_chunks=lambda ids: [chunk])
    citation = Citation(
        id="C1",
        passage_id="p1",
        document_id="doc1",
        revision=1,
        title="Source",
        quote="Tbilisi",
        location=SourceLocation(),
    )
    good = answer(
        citations=[citation], claims=[Claim(text="It runs in Tbilisi.", citation_ids=["C1"])]
    )
    metrics = score_case(case(), good, store)
    assert metrics["citation_source_validity"] == 1
    assert metrics["citation_gold_precision"] == 1
    assert metrics["claim_citation_coverage"] == 1
    bad = good.model_copy(deep=True)
    bad.citations[0].quote = "Batumi"
    bad.claims[0].citation_ids = ["made-up"]
    metrics = score_case(case(), bad, store)
    assert metrics["citation_source_validity"] == 0
    assert metrics["claim_citation_id_validity"] == 0


def test_required_facts_match_whole_tokens_not_substrings():
    scored = score_case(
        case(required_facts=[["17"], ["Orion", "Orion team"]]),
        answer(answer="117 requests were seen by Orion."),
    )
    assert scored["answer_fact_recall"] == 0.5


def test_conflicting_status_requires_actual_conflict_description():
    conflict_case = case(category="contradictory", expected_status="conflicting_evidence")
    assert (
        score_case(conflict_case, answer(status="conflicting_evidence"))["contradiction_accuracy"]
        == 0
    )
    assert (
        score_case(
            conflict_case,
            answer(
                status="conflicting_evidence",
                conflicts=[Conflict(description="Conflicting counts.")],
            ),
        )["contradiction_accuracy"]
        == 1
    )


def test_evaluation_exceptions_stay_in_denominators_and_do_not_expose_secrets(tmp_path):
    class Engine:
        calls = 0

        def investigate(self, request):
            self.calls += 1
            assert not request.use_cache
            if self.calls == 1:
                return answer()
            raise RuntimeError("secret=DO_NOT_PRINT_THIS_VALUE")

    report = evaluate(Engine(), [case(), case(id="two")], tmp_path)
    assert report["aggregate"]["answer_exact_match"] == 0.5
    assert report["aggregate"]["sample_counts"]["answer_exact_match"] == 2
    assert report["aggregate"]["error_rate"] == 0.5
    assert "DO_NOT_PRINT" not in (tmp_path / "results.json").read_text()
    assert report["rows"][1]["error"] == "RuntimeError"


def test_manifest_validation_rejects_duplicate_case_ids(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(case().model_dump_json() + "\n" + case().model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_cases(path)


def test_config_comparison_rejects_different_question_sets(tmp_path):
    class Engine:
        def investigate(self, request):
            return answer()

    evaluate(Engine(), [case()], tmp_path / "one", "one")
    evaluate(Engine(), [case(id="two")], tmp_path / "two", "two")
    with pytest.raises(ValueError, match="identical evaluation manifest"):
        compare_reports(
            [tmp_path / "one/results.json", tmp_path / "two/results.json"],
            tmp_path / "comparison.md",
        )


def test_benchmark_measures_actual_requests_and_validates_inputs(tmp_path):
    class Engine:
        calls = 0

        def investigate(self, request):
            self.calls += 1
            return answer()

    engine = Engine()
    report = run_benchmark(
        engine, ["Question one?", "Question two?"], tmp_path, repeats=2, concurrency=2
    )
    assert report["requests"] == 4
    assert engine.calls == 5
    assert report["latency_p95_ms"] >= report["latency_p50_ms"]
    assert report["rss_peak_sampled_bytes"] > 0
    assert report["corpus_stats"] is None
    assert percentile([1, 2, 3, 4], 0.95) == 4
    with pytest.raises(ValueError):
        run_benchmark(engine, [], tmp_path)


def test_ingestion_benchmark_distinguishes_existing_records_from_created(tmp_path):
    class Store:
        calls = 0

        def stats(self):
            self.calls += 1
            return {"documents": 49999 if self.calls == 1 else 50000, "chunks": 60000}

        def corpus_revision(self):
            return "after"

    class Ingestor:
        store = Store()
        settings = SimpleNamespace(
            embedding_model="test", embedding_backend="hash", chunk_strategy="fixed"
        )

        def ingest_records(self, records, batch_size=64):
            assert len(list(records)) == 2
            return {"processed": 2, "created": 1, "duplicates": 1, "failed": 0}

    report = run_ingestion_benchmark(Ingestor(), [{"id": "new"}, {"id": "existing"}], tmp_path)
    assert report["counts"]["created"] == 1
    assert report["active_document_delta"] == 1
    assert report["at_least_50000_active_documents"]
    assert report["created_records_per_second"] < report["processed_records_per_second"]

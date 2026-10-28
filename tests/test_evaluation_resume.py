"""Checkpoint tests use synthetic outcomes; they are not live-provider evidence."""

import json
from types import SimpleNamespace

import pytest

from investigation.config import Settings
from investigation.errors import ProviderError
from investigation.evaluation import EvaluationCase, compare_reports, evaluate
from investigation.models import InvestigationAnswer, InvestigationPlan


class Store:
    revision = "revision-one"

    def corpus_revision(self):
        return self.revision

    def stats(self):
        return {"documents": 2, "chunks": 2, "corpus_revision": self.revision}

    def get_chunks(self, ids):
        return []


class Engine:
    def __init__(self):
        self.settings = Settings(_env_file=None, environment="test", embedding_backend="hash")
        self.store = Store()
        self.calls = []
        self.next_error = None
        self.embedder = SimpleNamespace(fingerprint="hash:test-only")

    def investigate(self, request):
        self.calls.append(request.question)
        assert request.use_cache is False
        if self.next_error:
            error, self.next_error = self.next_error, None
            raise error
        return InvestigationAnswer(
            question=request.question,
            status="answered",
            answer="Tbilisi",
            plan=InvestigationPlan(subquestions=[request.question]),
            provider="extractive",
            model="test-only",
            corpus_revision=self.store.revision,
            retrieved_document_ids=["source"],
        )


def cases(count=3):
    return [
        EvaluationCase(
            id=f"case-{i}",
            category="direct",
            question=f"Where was service {i} running?",
            expected_answers=["Tbilisi"],
            gold_document_ids=["source"],
        )
        for i in range(count)
    ]


def test_batches_resume_without_repeating_completed_calls_and_preserve_predictions(tmp_path):
    engine = Engine()
    first = evaluate(engine, cases(), tmp_path, max_new_cases=1)
    assert first["status"] == "partial" and first["planned_case_count"] == 3
    assert first["case_count"] == 1 and len(engine.calls) == 1
    with pytest.raises(ValueError, match="Complete every planned"):
        compare_reports([tmp_path / "results.json"], tmp_path / "comparison.md")
    with pytest.raises(ValueError, match="checkpoint exists"):
        evaluate(engine, cases(), tmp_path)
    complete = evaluate(engine, cases(), tmp_path, resume=True)
    assert complete["status"] == "complete" and complete["case_count"] == 3
    assert len(engine.calls) == 3
    assert complete["rows"][0] == first["rows"][0]
    assert complete["run_id"] == first["run_id"]
    assert complete["duration_seconds"] >= first["duration_seconds"]
    evaluate(engine, cases(), tmp_path, resume=True)
    assert len(engine.calls) == 3


def test_ctrl_c_keeps_completed_rows_and_resumes_only_unfinished_work(tmp_path):
    engine = Engine()
    original = engine.investigate

    def interrupted(request):
        if len(engine.calls) == 1:
            raise KeyboardInterrupt()
        return original(request)

    engine.investigate = interrupted
    with pytest.raises(KeyboardInterrupt):
        evaluate(engine, cases(), tmp_path)
    saved = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert saved["status"] == "partial" and saved["case_count"] == 1
    engine.investigate = original
    result = evaluate(engine, cases(), tmp_path, resume=True)
    assert result["status"] == "complete" and len(engine.calls) == 3
    assert result["rows"][0] == saved["rows"][0]


def test_stop_after_provider_error_keeps_failure_without_retrying_it_on_resume(tmp_path):
    engine = Engine()
    engine.next_error = ProviderError("DO_NOT_RETAIN_SECRET")
    first = evaluate(engine, cases(), tmp_path, stop_on_error=True)
    assert first["status"] == "partial" and first["case_count"] == 1
    assert first["rows"][0]["error"] == "ProviderError"
    assert first["rows"][0]["metrics"]["elapsed_ms"] > 0
    assert "DO_NOT_RETAIN_SECRET" not in (tmp_path / "checkpoint.json").read_text()
    result = evaluate(engine, cases(), tmp_path, resume=True)
    assert len(engine.calls) == 3
    assert result["rows"][0] == first["rows"][0]
    assert result["aggregate"]["error_rate"] == pytest.approx(1 / 3)


@pytest.mark.parametrize("change", ["cases", "model", "corpus", "software", "embedding"])
def test_resume_rejects_changed_run_identity_without_overwriting_evidence(
    tmp_path, monkeypatch, change
):
    engine = Engine()
    questions = cases()
    evaluate(engine, questions, tmp_path, max_new_cases=1)
    original = (tmp_path / "checkpoint.json").read_bytes()
    if change == "cases":
        questions[-1] = questions[-1].model_copy(update={"expected_answers": ["Batumi"]})
    elif change == "model":
        engine.settings.llm_model = "changed-model"
    elif change == "corpus":
        engine.store.revision = "revision-two"
    elif change == "embedding":
        engine.embedder.fingerprint = "different-embedding"
    else:
        monkeypatch.setattr("investigation.evaluation.software_fingerprint", lambda: "changed")
    with pytest.raises(ValueError, match="Cannot resume"):
        evaluate(engine, questions, tmp_path, resume=True)
    assert len(engine.calls) == 1
    assert (tmp_path / "checkpoint.json").read_bytes() == original


def test_changed_corpus_during_last_case_invalidates_even_a_fully_populated_run(tmp_path):
    engine = Engine()
    original = engine.investigate

    def mutation(request):
        result = original(request)
        engine.store.revision = "changed"
        return result

    engine.investigate = mutation
    with pytest.raises(ValueError, match="Corpus changed during"):
        evaluate(engine, cases(1), tmp_path)
    saved = json.loads((tmp_path / "results.json").read_text())
    assert saved["status"] == "invalidated" and saved["case_count"] == 1
    engine.store.revision = "revision-one"
    with pytest.raises(ValueError, match="corpus changed during"):
        evaluate(engine, cases(1), tmp_path, resume=True)


def test_checkpoint_digest_rejects_accidental_prediction_edits(tmp_path):
    engine = Engine()
    evaluate(engine, cases(), tmp_path, max_new_cases=1)
    path = tmp_path / "checkpoint.json"
    checkpoint = json.loads(path.read_text())
    checkpoint["rows"][0]["answer"]["answer"] = "Changed text"
    path.write_text(json.dumps(checkpoint), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        evaluate(engine, cases(), tmp_path, resume=True)
    assert len(engine.calls) == 1


def test_pacing_can_change_between_sessions_without_changing_prediction_identity(tmp_path):
    engine = Engine()
    evaluate(engine, cases(), tmp_path, max_new_cases=1)
    engine.settings.llm_min_request_interval_seconds = 12
    result = evaluate(engine, cases(), tmp_path, resume=True)
    assert result["status"] == "complete"
    assert result["latest_session_policy"]["llm_min_request_interval_seconds"] == 12

import json
from types import SimpleNamespace

from typer.testing import CliRunner

from investigation.cli import app
from investigation.evaluation import EvaluationCase
from investigation.models import InvestigationAnswer, InvestigationPlan


def test_evaluate_cli_batches_resumes_and_selects_test_security_without_loading_models(
    tmp_path, monkeypatch
):
    questions = [
        EvaluationCase(
            id=split,
            category="direct",
            question=f"What is the {split} source fact?",
            expected_answers=["fact"],
            gold_document_ids=["source"],
            split=split,
        )
        for split in ["test", "tuning", "security"]
    ]
    source = tmp_path / "cases.jsonl"
    source.write_text("\n".join(case.model_dump_json() for case in questions), encoding="utf-8")
    calls, runtimes = [], []

    def investigate(request):
        calls.append(request.question)
        return InvestigationAnswer(
            question=request.question,
            status="answered",
            answer="fact",
            plan=InvestigationPlan(subquestions=[request.question]),
            provider="extractive",
            model="test-only",
            corpus_revision="fixture",
        )

    def build(settings):
        runtime = SimpleNamespace(
            engine=SimpleNamespace(settings=settings, investigate=investigate),
            closed=False,
        )
        runtime.close = lambda: setattr(runtime, "closed", True)
        runtimes.append(runtime)
        assert settings.llm_min_request_interval_seconds == 12
        return runtime

    monkeypatch.setattr("investigation.runtime.build_runtime", build)
    arguments = [
        "evaluate",
        str(source),
        "--output",
        str(tmp_path / "report"),
        "--split",
        "test-security",
        "--request-interval-seconds",
        "12",
    ]
    runner = CliRunner()
    partial = runner.invoke(app, [*arguments, "--max-new-cases", "1"])
    assert partial.exit_code == 2, partial.output
    assert json.loads(partial.output)["status"] == "partial"
    complete = runner.invoke(app, [*arguments, "--resume"])
    assert complete.exit_code == 0, complete.output
    assert json.loads(complete.output)["case_count"] == 2
    assert len(calls) == 2 and all("tuning" not in call for call in calls)
    assert all(runtime.closed for runtime in runtimes)

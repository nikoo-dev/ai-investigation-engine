import hashlib
import json

import httpx
import pytest
from pydantic import ValidationError

from investigation.config import Settings
from investigation.errors import ProviderError
from investigation.judge import RubricScore, judge_report
from investigation.llm import LLMClient as NativeLLMClient
from investigation.models import (
    Citation,
    Claim,
    InvestigationAnswer,
    InvestigationPlan,
    SourceLocation,
)


def configured(**overrides):
    return Settings(
        **{
            "_env_file": None,
            "environment": "test",
            "llm_provider": "gemini",
            "gemini_api_key": "JUDGE_PRIVATE_KEY_MUST_NOT_APPEAR",
            "llm_model": "judge-fixture-model",
            **overrides,
        }
    )


def source_row(identity="one", **answer_overrides):
    answer = InvestigationAnswer(
        **{
            "question": "What was the Atlas timeout?",
            "status": "answered",
            "answer": "The timeout was 250 milliseconds. [C1]",
            "claims": [Claim(text="The timeout was 250 milliseconds.", citation_ids=["C1"])],
            "citations": [
                Citation(
                    id="C1",
                    passage_id="p1",
                    document_id="d1",
                    revision=1,
                    title="Atlas evidence",
                    quote="250 milliseconds",
                    location=SourceLocation(),
                )
            ],
            "plan": InvestigationPlan(subquestions=["Atlas timeout"]),
            "model": "generator-model",
            "provider": "gemini",
            "corpus_revision": "r1",
            "trace": [{"stage": "debug", "detail": "HIDDEN_SYSTEM_PROMPT_MUST_NOT_APPEAR"}],
            **answer_overrides,
        }
    )
    return {
        "case": {
            "id": identity,
            "category": "direct",
            "question": "What was the Atlas timeout?",
            "expected_answers": ["250 milliseconds"],
            "required_facts": [["250"]],
            "gold_document_ids": ["d1"],
        },
        "answer": answer.model_dump(),
    }


def write_report(tmp_path, rows):
    path = tmp_path / "source.json"
    path.write_text(
        json.dumps(
            {
                "configuration": "test-run",
                "evaluation_sha256": "cases-hash",
                "settings": {
                    "api_key": "SOURCE_PRIVATE_KEY_MUST_NOT_APPEAR",
                    "embedding_backend": "fastembed",
                },
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )
    return path


class FixtureClient:
    prompts = []
    closed = False

    def __init__(self, settings):
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "retries": 0}

    def _structured(self, prompt, schema):
        self.prompts.append(prompt)
        self.usage["calls"] += 1
        return schema(
            correctness=0.8,
            groundedness=1,
            citation_support=0.9,
            reasoning_completeness=0.7,
            explanation="The stated timeout matches the reference and C1 supports the numeric claim.",
        )

    def close(self):
        type(self).closed = True


@pytest.fixture(autouse=True)
def fixture_client(monkeypatch):
    FixtureClient.prompts = []
    FixtureClient.closed = False
    monkeypatch.setattr("investigation.judge.LLMClient", FixtureClient)


def test_judge_sees_gold_and_saved_quotes_but_not_traces_settings_or_keys(tmp_path):
    source = write_report(tmp_path, [source_row()])
    original = source.read_bytes()
    report = judge_report(configured(), source, tmp_path / "review")
    prompt = FixtureClient.prompts[0]
    assert "250 milliseconds" in prompt and "reference_answers" in prompt
    assert "cited_source_quotes" in prompt and "C1" in prompt
    assert "HIDDEN_SYSTEM_PROMPT" not in prompt
    assert "SOURCE_PRIVATE_KEY" not in prompt and "JUDGE_PRIVATE_KEY" not in prompt
    assert source.read_bytes() == original
    assert report["source_report_sha256"] == hashlib.sha256(original).hexdigest()
    assert report["judged_case_count"] == 1 and report["error_case_count"] == 0
    assert report["all_selected_case_means"]["correctness"] == 0.8
    assert FixtureClient.closed
    assert (tmp_path / "review/judge-results.json").exists()
    assert (tmp_path / "review/judge-report.md").exists()


def test_judge_uses_actual_structured_provider_protocol_with_mocked_http(tmp_path, monkeypatch):
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        schema = payload["generationConfig"]["responseFormat"]["text"]["schema"]
        assert schema["properties"]["correctness"]["minimum"] == 0
        assert schema["properties"]["correctness"]["maximum"] == 1
        assert "tools" not in payload
        assert "JUDGE_PRIVATE_KEY" not in request.url.query.decode()
        score = {
            "correctness": 1,
            "groundedness": 1,
            "citation_support": 1,
            "reasoning_completeness": 1,
            "explanation": "The timeout agrees with the gold label and cited evidence.",
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": json.dumps(score)}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 123, "candidatesTokenCount": 21},
            },
        )

    monkeypatch.setattr(
        "investigation.judge.LLMClient",
        lambda settings: NativeLLMClient(settings, transport=httpx.MockTransport(handler)),
    )
    report = judge_report(configured(), write_report(tmp_path, [source_row()]), tmp_path / "review")
    assert len(requests) == 1
    assert report["usage"]["input_tokens"] == 123 and report["usage"]["output_tokens"] == 21
    assert report["all_selected_case_means"]["correctness"] == 1


def test_source_runtime_errors_stay_in_denominator_without_extra_llm_calls(tmp_path):
    failed = {"case": {"id": "failed"}, "answer": None, "error": "ProviderError"}
    source = write_report(
        tmp_path, [source_row(), failed, source_row("error-answer", status="error")]
    )
    report = judge_report(configured(), source, tmp_path / "review")
    assert len(FixtureClient.prompts) == 1
    assert report["score_denominators"] == {
        "all_selected_case_means": 3,
        "successful_judgment_means": 1,
    }
    assert report["all_selected_case_means"]["correctness"] == pytest.approx(0.8 / 3)
    assert report["successful_judgment_means"]["correctness"] == 0.8
    assert report["error_case_count"] == 2


def test_judge_errors_receive_no_quality_credit_and_raw_errors_are_not_saved(tmp_path, monkeypatch):
    def failing(self, prompt, schema):
        raise ProviderError("JUDGE_PRIVATE_KEY_MUST_NOT_APPEAR")

    monkeypatch.setattr(FixtureClient, "_structured", failing)
    source = write_report(tmp_path, [source_row()])
    report = judge_report(configured(), source, tmp_path / "review")
    assert report["error_case_count"] == 1
    assert report["all_selected_case_means"]["correctness"] == 0
    assert report["successful_judgment_means"]["correctness"] is None
    assert report["rows"][0]["error"] == "ProviderError"
    assert "JUDGE_PRIVATE_KEY" not in (tmp_path / "review/judge-results.json").read_text()
    assert FixtureClient.closed


def test_judge_rejects_extractive_provider_and_marks_extractive_source(tmp_path):
    source = write_report(tmp_path, [source_row(provider="extractive", model="source-excerpts")])
    with pytest.raises(ValueError, match="real Gemini or Ollama"):
        judge_report(configured(llm_provider="extractive"), source, tmp_path / "invalid")
    assert not FixtureClient.prompts
    report = judge_report(configured(), source, tmp_path / "review")
    assert report["source_preview_or_hash"]
    assert any("does not satisfy" in text for text in report["limitations"])


def test_same_generation_model_bias_and_limit_are_explicit(tmp_path):
    source = write_report(
        tmp_path, [source_row("one", model="judge-fixture-model"), source_row("two")]
    )
    report = judge_report(configured(), source, tmp_path / "review", limit=1)
    assert report["same_model_judge"]
    assert report["selected_case_count"] == 1 and report["not_selected_case_count"] == 1
    assert report["usage"]["calls"] == 1
    assert any("correlated errors" in text for text in report["limitations"])


def test_unanswerable_and_conflict_expected_statuses_are_part_of_rubric(tmp_path):
    one, two = (
        source_row("unknown", status="insufficient_evidence"),
        source_row("conflict", status="conflicting_evidence"),
    )
    one["case"].update(
        category="unanswerable",
        expected_status="insufficient_evidence",
        expected_answers=[],
        gold_document_ids=[],
    )
    two["case"].update(category="contradictory", expected_status="conflicting_evidence")
    judge_report(configured(), write_report(tmp_path, [one, two]), tmp_path / "review")
    assert '"expected_status": "insufficient_evidence"' in FixtureClient.prompts[0]
    assert '"expected_status": "conflicting_evidence"' in FixtureClient.prompts[1]
    assert "choosing an unsupported winner" in FixtureClient.prompts[1]


def test_judge_never_overwrites_source_or_existing_review(tmp_path):
    source = write_report(tmp_path, [source_row()])
    judge_report(configured(), source, tmp_path / "review")
    with pytest.raises(FileExistsError):
        judge_report(configured(), source, tmp_path / "review")
    duplicate = tmp_path / "judge-results.json"
    duplicate.write_bytes(source.read_bytes())
    with pytest.raises(ValueError, match="overwrite"):
        judge_report(configured(), duplicate, tmp_path)


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf")])
def test_rubric_rejects_invalid_score_ranges(value):
    with pytest.raises(ValidationError):
        RubricScore(
            correctness=value,
            groundedness=1,
            citation_support=1,
            reasoning_completeness=1,
            explanation="Reason",
        )


@pytest.mark.parametrize("limit", [0, -1, 501, True])
def test_limit_is_bounded_before_any_provider_call(tmp_path, limit):
    with pytest.raises(ValueError, match="limit"):
        judge_report(
            configured(), write_report(tmp_path, [source_row()]), tmp_path / "review", limit
        )
    assert not FixtureClient.prompts

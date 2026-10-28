"""Submission evidence tests use explicit synthetic artifacts and mock HTTP.

These fixtures test audit rules; they are not submitted as live-provider results.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from investigation.evaluation import EvaluationCase
from investigation.models import InvestigationAnswer, InvestigationPlan
from investigation.submission import REQUIRED_DOCUMENTS, audit_submission


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CountStore:
    def __init__(self, documents=50000):
        self.documents = documents

    def stats(self):
        return {
            "documents": self.documents,
            "chunks": self.documents,
            "corpus_revision": "revision",
        }


@pytest.fixture
def project(tmp_path):
    for filename in REQUIRED_DOCUMENTS:
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Synthetic test document.\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "--initial-branch=main", str(tmp_path)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Audit test",
            "-c",
            "user.email=audit@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "Test fixture",
        ],
        check=True,
    )
    commit = subprocess.check_output(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True
    ).strip()
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    corpus = dataset_dir / "corpus.jsonl"
    # This fixture checks manifest/hash rules, not source-dataset preparation.
    # A claimed preparation count is separately distinguished from Store counts.
    corpus.write_text('{"id":"fixture","text":"Synthetic audit artifact"}\n', encoding="utf-8")
    (dataset_dir / "cases.jsonl").write_text("{}\n", encoding="utf-8")
    write_json(
        dataset_dir / "manifest.json",
        {
            "records": 50000,
            "primary_records": 50000,
            "corpus_sha256": sha(corpus),
            "cases_sha256": sha(dataset_dir / "cases.jsonl"),
            "revision": "a" * 40,
            "seed": 42,
            "license": "CC0-1.0",
            "source_url": "https://corpus.example/dataset",
        },
    )
    rows = []
    for category in ["direct", "comparison", "multi_hop", "unanswerable", "contradictory"]:
        for index in range(8):
            status = (
                "insufficient_evidence"
                if category == "unanswerable"
                else "conflicting_evidence"
                if category == "contradictory"
                else "answered"
            )
            case = EvaluationCase(
                id=f"{category}-{index}",
                category=category,
                question=f"What is the source fact for {category} case {index}?",
                expected_status=status,
                expected_answers=[] if category == "unanswerable" else ["source fact"],
                gold_document_ids=[] if category == "unanswerable" else ["source-id"],
            )
            answer = InvestigationAnswer(
                question=case.question,
                status=status,
                answer="source fact",
                plan=InvestigationPlan(subquestions=[case.question]),
                provider="gemini",
                model="gemini-2.5-flash",
                corpus_revision="revision",
                usage={"calls": 2, "input_tokens": 500, "output_tokens": 100},
            )
            rows.append(
                {
                    "case": case.model_dump(),
                    "answer": answer.model_dump(),
                    "metrics": {"error_rate": 0},
                }
            )
    payload = "\n".join(
        EvaluationCase.model_validate(row["case"]).model_dump_json() for row in rows
    )
    report = {
        "case_count": len(rows),
        "evaluation_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "settings": {
            "embedding_backend": "fastembed",
            "embedding_model": "real-model",
            "llm_provider": "gemini",
            "llm_model": "gemini-2.5-flash",
            "chunk_strategy": "structure",
            "retrieval_mode": "hybrid",
        },
        "aggregate": {
            "recall_at_10": 0.8,
            "mrr": 0.8,
            "answer_token_f1": 0.8,
            "citation_source_validity": 1.0,
            "error_rate": 0.0,
        },
        "rows": rows,
    }
    write_json(tmp_path / "evaluation.json", report)
    for filename, field, value in [
        ("fixed.json", "chunk_strategy", "fixed"),
        ("dense.json", "retrieval_mode", "dense"),
    ]:
        comparison = deepcopy(report)
        comparison["settings"][field] = value
        write_json(tmp_path / filename, comparison)
    reviewed = []
    for category in ["direct", "comparison", "multi_hop", "unanswerable", "contradictory"]:
        for index in range(5):
            reviewed.append(
                {
                    "case_id": f"{category}-{index}",
                    "citation_entailment_checked": True,
                    "outcome": "supported",
                    "notes": "Synthetic audit-rule fixture, not a real human review.",
                }
            )
    write_json(
        tmp_path / "manual.json",
        {
            "reviewer_kind": "human",
            "reviewer": "Synthetic reviewer fixture",
            "approved": True,
            "reviewed_at": "2026-01-01T12:00:00+00:00",
            "evaluation_file_sha256": sha(tmp_path / "evaluation.json"),
            "cases": reviewed,
        },
    )
    now = datetime.now(UTC)
    capture = {
        "base_url": "https://demo.engine-demo.net",
        "captured_by": "Synthetic capture fixture",
        "health_before": {
            "status": "ok",
            "boot_id": str(uuid4()),
            "started_at": (now - timedelta(hours=4)).isoformat(),
        },
        "health_after": {
            "status": "ok",
            "boot_id": str(uuid4()),
            "started_at": (now - timedelta(hours=2)).isoformat(),
        },
        "observed_before_at": (now - timedelta(hours=3)).isoformat(),
        "observed_after_at": (now - timedelta(hours=1)).isoformat(),
        "document_before": {"id": str(uuid4()), "revision": 1, "checksum": "a" * 64},
    }
    capture["document_after"] = deepcopy(capture["document_before"])
    write_json(tmp_path / "deployment.json", capture)
    manifest = {
        "repository_url": "https://github.com/audit-user/investigation-engine",
        "live_demo_url": capture["base_url"],
        "dataset_manifest": "dataset/manifest.json",
        "evaluation_report": "evaluation.json",
        "comparison_reports": ["fixed.json", "dense.json"],
        "manual_review_report": "manual.json",
        "deployment_evidence": "deployment.json",
    }
    write_json(tmp_path / "submission.json", manifest)
    return {
        "root": tmp_path,
        "manifest": manifest,
        "report": report,
        "capture": capture,
        "commit": commit,
    }


def install_http(monkeypatch, project, *, redirect=False, changed_document=False):
    original = httpx.Client
    requests = []

    def handle(request):
        requests.append(str(request.url))
        if "/commits/" in request.url.path:
            return httpx.Response(200, json={"sha": project["commit"]})
        if request.url.path == "/health":
            if redirect:
                return httpx.Response(302, headers={"Location": "https://127.0.0.1/health"})
            return httpx.Response(200, json=project["capture"]["health_after"])
        if request.url.path == "/ready":
            return httpx.Response(200, json={"status": "ready"})
        if request.url.path.startswith("/api/v1/documents/"):
            doc = {**project["capture"]["document_after"], "status": "ready"}
            if changed_document:
                doc["checksum"] = "b" * 64
            return httpx.Response(200, json=doc)
        return httpx.Response(404)

    def client(**kwargs):
        assert kwargs["timeout"] == 5
        assert kwargs["follow_redirects"] is False
        return original(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr("investigation.submission.httpx.Client", client)
    return requests


def checks(result):
    return {check["id"]: check for check in result["checks"]}


def test_missing_manifest_reports_all_submission_gaps_without_initializing_runtime(tmp_path):
    result = audit_submission(tmp_path, Path("missing.json"))
    by_id = checks(result)
    assert result["status"] == "incomplete"
    assert len(by_id) == 11
    assert all(check["status"] == "incomplete" for check in by_id.values())
    assert "no Store" in by_id["active_corpus"]["detail"]


def test_offline_audit_never_contacts_urls_or_assumes_reported_counts_are_live(
    project, monkeypatch
):
    def forbidden(**kwargs):
        raise AssertionError("Offline audit must not contact any URL")

    monkeypatch.setattr("investigation.submission.httpx.Client", forbidden)
    result = audit_submission(project["root"], Path("submission.json"))
    by_id = checks(result)
    assert result["status"] == "incomplete"
    assert by_id["dataset_manifest"]["status"] == "pass"
    assert by_id["live_llm_evaluation"]["status"] == "pass"
    assert by_id["active_corpus"]["status"] == "incomplete"
    assert by_id["public_live_demo"]["status"] == "incomplete"
    assert by_id["restart_persistence"]["status"] == "incomplete"


def test_complete_synthetic_artifact_package_requires_current_source_and_remote_commit(
    project, monkeypatch
):
    requested = install_http(monkeypatch, project)
    result = audit_submission(project["root"], Path("submission.json"), CountStore(), True)
    assert result["status"] == "pass", result
    assert len(requested) == 4
    assert (
        checks(result)["restart_persistence"]["evidence_level"]
        == "captured_transition_and_current_http"
    )
    assert checks(result)["manual_answer_review"]["evidence_level"] == "human_attestation"
    assert "not independently rerun" in result["limitations"][0]


@pytest.mark.parametrize(
    "provider,backend,calls",
    [("extractive", "fastembed", 2), ("gemini", "hash", 2), ("gemini", "fastembed", 0)],
)
def test_preview_or_zero_call_evaluation_cannot_satisfy_live_llm_gate(
    project, provider, backend, calls
):
    report = project["report"]
    report["settings"]["llm_provider"] = provider
    report["settings"]["embedding_backend"] = backend
    for row in report["rows"]:
        row["answer"]["provider"] = provider
        row["answer"]["usage"]["calls"] = calls
    write_json(project["root"] / "evaluation.json", report)
    result = audit_submission(project["root"], Path("submission.json"), CountStore())
    assert checks(result)["live_llm_evaluation"]["status"] == "incomplete"


def test_errors_stay_in_case_count_and_prevent_false_success(project):
    report = project["report"]
    report["rows"][0]["answer"] = None
    report["rows"][0]["error"] = "TimeoutException"
    report["aggregate"]["error_rate"] = 1 / 40
    write_json(project["root"] / "evaluation.json", report)
    result = audit_submission(project["root"], Path("submission.json"), CountStore())
    detail = checks(result)["live_llm_evaluation"]["detail"]
    assert "live=39" in detail and "errors=1" in detail


def test_honest_retained_failure_does_not_disqualify_forty_completed_live_cases(project):
    report = project["report"]
    failed = deepcopy(report["rows"][0])
    failed["case"]["id"] = "additional-failed-case"
    failed["answer"] = None
    failed["error"] = "ProviderError"
    failed["metrics"] = {"error_rate": 1}
    report["rows"].append(failed)
    report["case_count"] = 41
    report["aggregate"]["error_rate"] = 1 / 41
    report["evaluation_sha256"] = hashlib.sha256(
        "\n".join(
            EvaluationCase.model_validate(row["case"]).model_dump_json() for row in report["rows"]
        ).encode()
    ).hexdigest()
    write_json(project["root"] / "evaluation.json", report)
    result = audit_submission(project["root"], Path("submission.json"), CountStore())
    gate = checks(result)["live_llm_evaluation"]
    assert gate["status"] == "pass", gate
    assert gate["evidence"]["errors"] == 1
    assert gate["evidence"]["live_test_cases"] == 40


@pytest.mark.parametrize("status", ["partial", "invalidated"])
def test_partial_or_invalidated_evaluation_cannot_pass_submission_gate(project, status):
    report = project["report"]
    report["status"] = status
    write_json(project["root"] / "evaluation.json", report)
    result = audit_submission(project["root"], Path("submission.json"), CountStore())
    assert "every planned case" in checks(result)["live_llm_evaluation"]["detail"]


def test_duplicate_case_ids_and_changed_hash_are_rejected(project):
    report = project["report"]
    report["rows"][1]["case"]["id"] = report["rows"][0]["case"]["id"]
    write_json(project["root"] / "evaluation.json", report)
    result = audit_submission(project["root"], Path("submission.json"), CountStore())
    assert "Repeated question IDs" in checks(result)["live_llm_evaluation"]["detail"]


def test_available_dataset_files_are_hash_checked(project):
    corpus = project["root"] / "dataset/corpus.jsonl"
    with corpus.open("a", encoding="utf-8") as stream:
        stream.write("tampered\n")
    result = audit_submission(project["root"], Path("submission.json"), CountStore())
    assert "hashes do not match" in checks(result)["dataset_manifest"]["detail"]


def test_active_database_count_cannot_be_replaced_by_dataset_or_report_count(project):
    result = audit_submission(project["root"], Path("submission.json"), CountStore(49999))
    assert checks(result)["dataset_manifest"]["status"] == "pass"
    assert checks(result)["active_corpus"]["status"] == "incomplete"


def test_manual_review_needs_matching_file_and_actual_case_findings(project):
    path = project["root"] / "manual.json"
    manual = json.loads(path.read_text())
    manual["cases"][0]["case_id"] = "invented-question"
    write_json(path, manual)
    result = audit_submission(project["root"], Path("submission.json"), CountStore())
    assert checks(result)["manual_answer_review"]["status"] == "incomplete"


def test_redirect_to_local_address_is_not_followed(project, monkeypatch):
    requested = install_http(monkeypatch, project, redirect=True)
    result = audit_submission(project["root"], Path("submission.json"), CountStore(), True)
    assert checks(result)["public_live_demo"]["status"] == "incomplete"
    assert not any("127.0.0.1" in url for url in requested)


def test_operator_claim_without_captured_instances_cannot_prove_restart(project, monkeypatch):
    install_http(monkeypatch, project)
    write_json(
        project["root"] / "deployment.json",
        {
            "base_url": project["manifest"]["live_demo_url"],
            "operator": "Someone",
            "restarted": True,
        },
    )
    result = audit_submission(project["root"], Path("submission.json"), CountStore(), True)
    assert checks(result)["restart_persistence"]["status"] == "incomplete"


def test_same_boot_id_is_not_a_restart(project, monkeypatch):
    capture = project["capture"]
    capture["health_before"]["boot_id"] = capture["health_after"]["boot_id"]
    write_json(project["root"] / "deployment.json", capture)
    install_http(monkeypatch, project)
    result = audit_submission(project["root"], Path("submission.json"), CountStore(), True)
    assert "distinct application instances" in checks(result)["restart_persistence"]["detail"]


def test_changed_current_document_fails_persistence_check(project, monkeypatch):
    install_http(monkeypatch, project, changed_document=True)
    result = audit_submission(project["root"], Path("submission.json"), CountStore(), True)
    assert "does not match" in checks(result)["restart_persistence"]["detail"]


def test_artifact_path_escape_is_rejected(project):
    manifest = project["manifest"]
    manifest["evaluation_report"] = "../outside.json"
    write_json(project["root"] / "submission.json", manifest)
    result = audit_submission(project["root"], Path("submission.json"), CountStore())
    assert "inside the project directory" in checks(result)["live_llm_evaluation"]["detail"]


def test_ollama_latest_tag_is_not_misclassified_as_test_model(project):
    report = project["report"]
    report["settings"]["llm_provider"] = "ollama"
    report["settings"]["llm_model"] = "qwen3:latest"
    for row in report["rows"]:
        row["answer"]["provider"] = "ollama"
        row["answer"]["model"] = "qwen3:latest"
    write_json(project["root"] / "evaluation.json", report)
    result = audit_submission(project["root"], Path("submission.json"), CountStore())
    assert checks(result)["live_llm_evaluation"]["status"] == "pass"


@pytest.mark.parametrize("field,value", [("settings", []), ("aggregate", []), ("rows", "invalid")])
def test_malformed_report_objects_leave_audit_incomplete_instead_of_crashing(project, field, value):
    report = project["report"]
    report[field] = value
    write_json(project["root"] / "evaluation.json", report)
    result = audit_submission(project["root"], Path("submission.json"), CountStore())
    assert checks(result)["live_llm_evaluation"]["status"] == "incomplete"


def test_committed_preparation_manifest_can_report_raw_files_unverified(project):
    metadata = json.loads((project["root"] / "dataset/manifest.json").read_text())
    write_json(project["root"] / "data/manifests/hotpot-50k.json", metadata)
    manifest = project["manifest"]
    manifest["dataset_manifest"] = "data/manifests/hotpot-50k.json"
    write_json(project["root"] / "submission.json", manifest)
    result = audit_submission(project["root"], Path("submission.json"), CountStore())
    evidence = checks(result)["dataset_manifest"]["evidence"]
    assert checks(result)["dataset_manifest"]["status"] == "pass"
    assert evidence["file_hashes_verified"] is False
    assert evidence["record_count_independently_recounted"] is False


def test_store_failure_does_not_expose_external_exception_text(project):
    class BrokenStore:
        def stats(self):
            raise ValueError("credential=do-not-expose")

    result = audit_submission(project["root"], Path("submission.json"), BrokenStore())
    assert checks(result)["active_corpus"]["status"] == "incomplete"
    assert "do-not-expose" not in json.dumps(result)


def test_preparation_count_below_minimum_cannot_satisfy_dataset_gate(project):
    path = project["root"] / "dataset/manifest.json"
    metadata = json.loads(path.read_text())
    metadata["primary_records"] = 49999
    write_json(path, metadata)
    result = audit_submission(project["root"], Path("submission.json"), CountStore())
    assert checks(result)["dataset_manifest"]["status"] == "incomplete"

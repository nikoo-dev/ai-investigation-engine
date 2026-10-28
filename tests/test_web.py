"""HTTP contracts and security boundaries tested without external services."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from investigation.config import Settings
from investigation.errors import InvalidDocument, ProviderError
from investigation.models import (
    Chunk,
    Document,
    IngestionResult,
    InvestigationAnswer,
    InvestigationPlan,
    InvestigationRequest,
    SourceLocation,
)
from investigation.web import RateLimiter, create_app


class FakeStore:
    def __init__(self):
        self.doc = Document(
            id="document-1",
            title="A public report",
            filename="report.txt",
            format="txt",
            checksum="checksum",
            text="Payments are delayed.",
            status="ready",
            chunk_count=1,
        )
        self.deleted = False
        self.unavailable = False

    def stats(self):
        if self.unavailable:
            raise RuntimeError("database unavailable")
        return {"documents": 0 if self.deleted else 1, "chunks": 0 if self.deleted else 1}

    def list_documents(self, limit=50, offset=0):
        return [] if self.deleted or offset else [self.doc][:limit]

    def get_document(self, document_id):
        return self.doc if document_id == self.doc.id and not self.deleted else None

    def delete_document(self, document_id):
        if not self.get_document(document_id):
            return False
        self.deleted = True
        return True

    def get_chunks(self, passage_ids):
        if self.deleted or "passage-1" not in passage_ids:
            return []
        return [
            Chunk(
                id="passage-1",
                document_id=self.doc.id,
                revision=self.doc.revision,
                title=self.doc.title,
                text=self.doc.text,
                checksum="checksum",
                location=SourceLocation(page=1),
            )
        ]

    def get_job(self, job_id):
        return None


class FakeIngestion:
    def __init__(self, store):
        self.store = store
        self.filename = None

    def ingest(self, filename, content, document_id=None):
        self.filename = filename
        if filename.endswith(".exe"):
            raise InvalidDocument("Unsupported document format.")
        self.store.doc = self.store.doc.model_copy(
            update={
                "filename": filename,
                "text": content.decode(),
                "revision": self.store.doc.revision + (1 if document_id else 0),
            }
        )
        return IngestionResult(
            status="updated" if document_id else "created", document=self.store.doc
        )


class FakeEngine:
    def __init__(self):
        self.failure = None
        self.events = None

    def investigate(self, request):
        if self.failure:
            raise self.failure
        return InvestigationAnswer(
            question=request.question,
            status="answered",
            answer="The report records payment delays.",
            plan=InvestigationPlan(subquestions=[request.question]),
            model="test-model",
            provider="test",
            corpus_revision="1",
        )

    def stream(self, request):
        if self.events is not None:
            yield from self.events
            return
        yield {"event": "progress", "data": {"stage": "retrieval", "detail": "Finding evidence"}}
        yield {"event": "token", "data": {"text": "unchecked model text"}}
        yield {"event": "final", "data": self.investigate(request).model_dump()}


@pytest.fixture
def services():
    store = FakeStore()
    return store, FakeIngestion(store), FakeEngine()


def client_for(services, **overrides):
    store, ingestion, engine = services
    settings = Settings(
        _env_file=None,
        environment="test",
        embedding_backend="hash",
        requests_per_minute=100,
        **overrides,
    )
    return TestClient(
        create_app(settings, engine=engine, ingestion=ingestion, store=store),
        raise_server_exceptions=False,
    )


def test_liveness_readiness_status_and_metrics(services):
    with client_for(services) as client:
        health = client.get("/health").json()
        assert health["status"] == "ok"
        assert health["boot_id"]
        assert health["started_at"]
        assert client.get("/ready").json() == {"status": "ready"}
        status = client.get("/api/v1/status").json()
        assert status["corpus"]["documents"] == 1
        assert "api_key" not in str(status)
        assert "investigation_http_requests_total" in client.get("/metrics").text
        services[0].unavailable = True
        assert client.get("/ready").status_code == 503


def test_document_lifecycle_and_bounded_listing(services):
    with client_for(services) as client:
        listed = client.get("/api/v1/documents").json()["items"]
        assert listed[0]["id"] == "document-1"
        assert "text" not in listed[0]
        assert "blocks" not in listed[0]
        assert client.get("/api/v1/documents?limit=101").status_code == 422
        assert client.get("/api/v1/documents?offset=-1").status_code == 422
        assert client.get("/api/v1/documents/document-1").json()["text"]
        assert client.get("/api/v1/passages/passage-1").json()["location"]["page"] == 1
        created = client.post("/api/v1/documents", files={"file": ("test.txt", b"New text")})
        assert created.status_code == 201
        assert created.json()["status"] == "created"
        replaced = client.put(
            "/api/v1/documents/document-1", files={"file": ("revised.txt", b"Revised")}
        )
        assert replaced.status_code == 200
        assert replaced.json()["document"]["revision"] == 2
        assert client.delete("/api/v1/documents/document-1").status_code == 204
        assert client.get("/api/v1/documents/document-1").status_code == 404
        assert client.get("/api/v1/passages/passage-1").status_code == 404
        assert client.delete("/api/v1/documents/document-1").status_code == 404


def test_mutations_require_configured_token_but_public_reads_do_not(services):
    with client_for(services, admin_token=SecretStr("secret-management-token")) as client:
        assert client.get("/api/v1/documents").status_code == 200
        assert (
            client.post("/api/v1/documents", files={"file": ("new.txt", b"text")}).status_code
            == 401
        )
        assert (
            client.delete(
                "/api/v1/documents/document-1", headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )
        response = client.post(
            "/api/v1/documents",
            files={"file": ("new.txt", b"text")},
            headers={"Authorization": "Bearer secret-management-token"},
        )
        assert response.status_code == 201
        assert client.get("/api/v1/status").json()["management_protected"]
        malformed = client.post(
            "/api/v1/documents",
            content=b"not multipart",
            headers={"Content-Type": "multipart/form-data"},
        )
        assert malformed.status_code == 401


def test_upload_validation_and_filename_sanitization(services):
    with client_for(services, max_upload_mb=1) as client:
        assert (
            client.post("/api/v1/documents", files={"file": ("empty.txt", b"")}).status_code == 422
        )
        assert (
            client.post(
                "/api/v1/documents", files={"file": ("big.txt", b"x" * (1024 * 1024 + 1))}
            ).status_code
            == 413
        )
        assert (
            client.post("/api/v1/documents", files={"file": ("run.exe", b"data")}).status_code
            == 422
        )
        assert (
            client.put(
                "/api/v1/documents/missing", files={"file": ("new.txt", b"text")}
            ).status_code
            == 404
        )
        response = client.post(
            "/api/v1/documents", files={"file": ("../../folder/report.txt", b"data")}
        )
        assert response.status_code == 201
        assert services[1].filename == "report.txt"


def test_investigation_validation_response_and_errors(services):
    with client_for(services) as client:
        response = client.post(
            "/api/v1/investigations", json={"question": "Why are payments delayed?"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "answered"
        assert response.headers["X-Request-ID"]
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert client.post("/api/v1/investigations", json={"question": "x"}).status_code == 422
        services[2].failure = ProviderError("The model request timed out.")
        failure = client.post(
            "/api/v1/investigations", json={"question": "Investigate the timeout"}
        )
        assert failure.status_code == 503
        assert failure.json()["error"]["code"] == "provider_unavailable"


def test_stream_contains_only_validated_answer_and_safe_event_names(services):
    with client_for(services) as client:
        response = client.post(
            "/api/v1/investigations/stream", json={"question": "Why are payments delayed?"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: progress" in response.text
        assert "event: final" in response.text
        assert "unchecked model text" not in response.text
        services[2].events = [{"event": "evil\nevent: forged", "data": {"detail": "safe"}}]
        safe = client.post("/api/v1/investigations/stream", json={"question": "Another question"})
        assert "event: progress" in safe.text
        assert "forged" not in safe.text


def test_invalid_final_stream_does_not_escape_validation(services):
    services[2].events = [{"event": "final", "data": {"answer": "Unchecked"}}]
    with client_for(services) as client:
        response = client.post(
            "/api/v1/investigations/stream", json={"question": "Why are payments delayed?"}
        )
        assert "event: error" in response.text
        assert "event: final" not in response.text
        assert "event: answer_fragment" not in response.text
        assert "Unchecked" not in response.text


def test_stream_fragments_reconstruct_validated_answer_before_structured_final(services):
    question = "Why are payments delayed?"
    answer = services[2].investigate(InvestigationRequest(question=question))
    answer.answer = ("Verified source finding [C1]. " * 13) + "\nUnicode evidence: ქართული ✓"
    services[2].events = [
        {
            "event": "stage",
            "data": {"stage": "verification", "message": "Checking source evidence"},
        },
        {"event": "token", "data": {"text": "UNVERIFIED_PROVIDER_TOKEN"}},
        {"event": "answer_fragment", "data": {"text": "UNVALIDATED_ENGINE_FRAGMENT"}},
        {"event": "answer", "data": answer.model_dump()},
    ]
    with client_for(services) as client:
        response = client.post("/api/v1/investigations/stream", json={"question": question})
    events = []
    for block in response.text.strip().split("\n\n"):
        lines = block.splitlines()
        events.append(
            (lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: ")))
        )
    fragments = [data["text"] for event, data in events if event == "answer_fragment"]
    assert len(fragments) > 1
    assert all(0 < len(fragment) <= 120 for fragment in fragments)
    assert "".join(fragments) == answer.answer
    assert events[0][0] == "stage"
    assert all(event == "answer_fragment" for event, _ in events[1:-1])
    assert events[-1][0] == "final"
    assert events[-1][1]["answer"] == answer.answer
    assert "UNVERIFIED_PROVIDER_TOKEN" not in response.text
    assert "UNVALIDATED_ENGINE_FRAGMENT" not in response.text


def test_invalid_final_does_not_allow_prior_engine_fragment_or_provider_token(services):
    services[2].events = [
        {"event": "token", "data": {"text": "UNVERIFIED_PROVIDER_TOKEN"}},
        {"event": "answer_fragment", "data": {"text": "UNVALIDATED_ENGINE_FRAGMENT"}},
        {"event": "answer", "data": {"answer": "Invalid incomplete final"}},
    ]
    with client_for(services) as client:
        response = client.post(
            "/api/v1/investigations/stream", json={"question": "Inspect source evidence"}
        )
    assert "event: error" in response.text
    assert "event: answer_fragment" not in response.text
    assert "event: final" not in response.text
    assert "UNVALIDATED" not in response.text
    assert "UNVERIFIED" not in response.text


def test_server_error_does_not_disclose_internal_exception(services):
    services[2].failure = RuntimeError("credential=do-not-leak")
    with client_for(services) as client:
        response = client.post(
            "/api/v1/investigations", json={"question": "Why are payments delayed?"}
        )
        assert response.status_code == 500
        assert "do-not-leak" not in response.text


def test_home_escapes_configured_title_and_sets_csp(services):
    with client_for(services, app_name="<script>window.bad=1</script>") as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "<script>window.bad=1</script>" not in response.text
        assert "&lt;script&gt;window.bad=1&lt;/script&gt;" in response.text
        assert "script-src 'self'" in response.headers["Content-Security-Policy"]
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/static/app.css").status_code == 200


def test_rate_limiter_is_bounded_and_ignores_forwarded_headers(services):
    limiter = RateLimiter(limit=1, max_clients=2)
    limiter.check("a")
    limiter.check("b")
    limiter.check("c")
    assert len(limiter.clients) == 2
    assert "a" not in limiter.clients
    app = create_app(
        Settings(_env_file=None, environment="test", requests_per_minute=1),
        engine=services[2],
        ingestion=services[1],
        store=services[0],
    )
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/investigations",
                json={"question": "First query"},
                headers={"X-Forwarded-For": "1.2.3.4"},
            ).status_code
            == 200
        )
        response = client.post(
            "/api/v1/investigations",
            json={"question": "Second query"},
            headers={"X-Forwarded-For": "4.3.2.1"},
        )
        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) > 0
        assert client.get("/health").status_code == 200


def test_unknown_job_and_missing_source_return_not_found(services):
    with client_for(services) as client:
        assert client.get("/api/v1/jobs/missing").status_code == 404
        assert client.get("/api/v1/documents/missing").status_code == 404
        assert client.get("/api/v1/passages/missing").status_code == 404


def test_upload_body_is_bounded_before_multipart_parsing(services):
    with client_for(services, max_upload_mb=1) as client:
        response = client.post(
            "/api/v1/documents",
            content=b"x" * (2 * 1024 * 1024),
            headers={"Content-Type": "multipart/form-data; boundary=test"},
        )
        assert response.status_code == 413
        streamed = client.post(
            "/api/v1/documents",
            content=iter([b"--test\r\n", b"x" * (2 * 1024 * 1024)]),
            headers={"Content-Type": "multipart/form-data; boundary=test"},
        )
        assert streamed.status_code == 413


def test_complete_investigation_metrics_include_outcomes_latency_and_tokens(services):
    with client_for(services) as client:
        client.post("/api/v1/investigations", json={"question": "Why are payments delayed?"})
        client.post("/api/v1/investigations/stream", json={"question": "Why are payments delayed?"})
        metrics = client.get("/metrics").text
        assert 'investigation_answers_total{provider="extractive",status="answered"} 2.0' in metrics
        assert "investigation_duration_seconds_count" in metrics
        assert "investigation_llm_tokens_total" in metrics


def test_real_runtime_upload_search_source_and_restart_persistence(tmp_path):
    """Exercise actual local Qdrant and pipeline through the HTTP boundary.

    Hash vectors keep this an offline plumbing test; semantic quality is measured
    separately with real models, never inferred from this fixture.
    """
    settings = Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path,
        embedding_backend="hash",
        embedding_dimension=64,
        reranker_enabled=False,
        llm_provider="extractive",
        requests_per_minute=100,
    )
    with TestClient(create_app(settings)) as client:
        first_health = client.get("/health").json()
        upload = client.post(
            "/api/v1/documents",
            files={
                "file": (
                    "atlas.txt",
                    b"Atlas CHG-001 reduced payments-gateway timeout to 250 milliseconds. "
                    b"The rollback restored payment processing after the timeout incident.",
                )
            },
        )
        assert upload.status_code == 201
        document_id = upload.json()["document"]["id"]
        response = client.post(
            "/api/v1/investigations",
            json={
                "question": "What reduced payments-gateway timeout to 250 milliseconds?",
            },
        )
        assert response.status_code == 200
        answer = response.json()
        assert answer["provider"] == "extractive"
        assert answer["citations"]
        citation = answer["citations"][0]
        passage_id = citation["passage_id"]
        passage = client.get(f"/api/v1/passages/{passage_id}").json()
        assert citation["quote"] in passage["text"]
        assert citation["document_id"] == document_id
        assert client.get("/api/v1/status").json()["corpus"]["documents"] == 1
    # Closing/reopening the process services must preserve source data.
    with TestClient(create_app(settings)) as restarted:
        second_health = restarted.get("/health").json()
        assert first_health["boot_id"] != second_health["boot_id"]
        assert second_health["started_at"] >= first_health["started_at"]
        assert restarted.get(f"/api/v1/documents/{document_id}").status_code == 200
        assert restarted.get(f"/api/v1/passages/{passage_id}").status_code == 200
        assert restarted.delete(f"/api/v1/documents/{document_id}").status_code == 204
        assert restarted.get(f"/api/v1/passages/{passage_id}").status_code == 404

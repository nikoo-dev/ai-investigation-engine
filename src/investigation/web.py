"""HTTP boundary and same-origin workstation UI.

The application factory accepts injected services so route/security tests do not
download a model or require an external database.
"""

from __future__ import annotations

import json
import logging
import secrets
import time
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

from investigation.config import Settings
from investigation.errors import EngineError
from investigation.models import InvestigationAnswer, InvestigationRequest, utc_now

LOGGER = logging.getLogger(__name__)
PACKAGE = Path(__file__).parent


class _UploadBodyTooLarge(HTTPException):
    def __init__(self):
        super().__init__(status_code=413, detail="The upload request is too large.")


class UploadBoundaryMiddleware:
    """Reject unauthenticated or excessive uploads before multipart spooling.

    The whole HTTP body has a small allowance for multipart headers; the file
    itself is checked separately at its exact configured limit.
    """

    def __init__(self, app: ASGIApp, max_bytes: int, token: str | None):
        self.app = app
        self.max_bytes = max_bytes
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        mutation = (
            scope["type"] == "http"
            and scope.get("method") in {"POST", "PUT", "DELETE"}
            and (path == "/api/v1/documents" or path.startswith("/api/v1/documents/"))
        )
        if not mutation:
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        if self.token:
            supplied = headers.get(b"authorization", b"")
            if not secrets.compare_digest(supplied, ("Bearer " + self.token).encode()):
                await JSONResponse(
                    {"detail": "A valid management token is required."},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )(scope, receive, send)
                return
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            await JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)(
                scope, receive, send
            )
            return
        if length > self.max_bytes:
            await JSONResponse({"detail": "The upload request is too large."}, status_code=413)(
                scope, receive, send
            )
            return
        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_bytes:
                    raise _UploadBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _UploadBodyTooLarge:
            await JSONResponse({"detail": "The upload request is too large."}, status_code=413)(
                scope, receive, send
            )


class RateLimiter:
    """Bounded sliding window per direct peer address, shared across guarded routes."""

    def __init__(self, limit: int, window_seconds: float = 60, max_clients: int = 4096):
        self.limit = limit
        self.window = window_seconds
        self.max_clients = max_clients
        self.clients: OrderedDict[str, deque[float]] = OrderedDict()
        self.lock = Lock()

    def check(self, address: str) -> None:
        now = time.monotonic()
        with self.lock:
            events = self.clients.pop(address, deque())
            while events and events[0] <= now - self.window:
                events.popleft()
            self.clients[address] = events
            while len(self.clients) > self.max_clients:
                self.clients.popitem(last=False)
            if len(events) >= self.limit:
                retry_after = max(1, int(self.window - (now - events[0])) + 1)
                raise HTTPException(
                    status_code=429,
                    detail="Request limit reached. Please try again shortly.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)


def create_app(
    settings: Settings | None = None,
    engine: Any = None,
    ingestion: Any = None,
    store: Any = None,
) -> FastAPI:
    configuration = settings or Settings()
    limiter = RateLimiter(configuration.requests_per_minute)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.boot_id = str(uuid4())
        app.state.started_at = utc_now()
        runtime = None
        if engine is None or ingestion is None or store is None:
            from investigation.runtime import build_runtime

            runtime = await run_in_threadpool(build_runtime, configuration)
            app.state.engine = engine if engine is not None else runtime.engine
            app.state.ingestion = ingestion if ingestion is not None else runtime.ingestion
            app.state.store = store if store is not None else runtime.store
        app.state.ready = True
        try:
            yield
        finally:
            app.state.ready = False
            if runtime is not None:
                await run_in_threadpool(runtime.close)

    app = FastAPI(
        title=configuration.app_name,
        version="0.1.0",
        description="Evidence-driven investigations over a versioned hybrid search corpus.",
        lifespan=lifespan,
    )
    app.state.settings = configuration
    app.state.store = store
    app.state.ingestion = ingestion
    app.state.engine = engine
    app.state.ready = False
    app.state.boot_id = None
    app.state.started_at = None
    app.state.rate_limiter = limiter

    registry = CollectorRegistry()
    request_count = Counter(
        "investigation_http_requests_total",
        "HTTP requests",
        ["method", "route", "status"],
        registry=registry,
    )
    request_time = Histogram(
        "investigation_http_duration_seconds",
        "HTTP request duration",
        ["method", "route"],
        registry=registry,
    )
    answer_count = Counter(
        "investigation_answers_total",
        "Completed investigations by outcome",
        ["status", "provider"],
        registry=registry,
    )
    investigation_time = Histogram(
        "investigation_duration_seconds",
        "Complete investigation duration",
        ["provider"],
        registry=registry,
    )
    llm_tokens = Counter(
        "investigation_llm_tokens_total",
        "Consumed LLM tokens",
        ["direction", "provider"],
        registry=registry,
    )
    stage_time = Histogram(
        "investigation_stage_duration_seconds",
        "Investigation stage duration",
        ["stage"],
        registry=registry,
    )
    app.add_middleware(
        UploadBoundaryMiddleware,
        max_bytes=configuration.max_upload_mb * 1024 * 1024 + 64 * 1024,
        token=configuration.admin_token.get_secret_value() if configuration.admin_token else None,
    )
    if configuration.allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=configuration.allow_origins,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
            allow_credentials=False,
        )

    @app.middleware("http")
    async def instrumentation(request: Request, call_next):
        started = time.perf_counter()
        request_id = str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        route = request.scope.get("route")
        route_label = getattr(route, "path", "unmatched")
        elapsed = time.perf_counter() - started
        request_count.labels(request.method, route_label, str(response.status_code)).inc()
        request_time.labels(request.method, route_label).observe(elapsed)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        LOGGER.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "route": route_label,
                    "status": response.status_code,
                    "duration_ms": round(elapsed * 1000, 2),
                }
            )
        )
        return response

    @app.exception_handler(EngineError)
    async def engine_error(request: Request, exc: EngineError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                    "request_id": request.state.request_id,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        LOGGER.exception("Unexpected request error; request_id=%s", request.state.request_id)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "The request could not be completed.",
                    "request_id": request.state.request_id,
                }
            },
        )

    def guarded(request: Request) -> None:
        peer = request.client.host if request.client else "unknown"
        limiter.check(peer)

    def authorize_write(request: Request) -> None:
        token = configuration.admin_token
        if token:
            supplied = request.headers.get("Authorization", "")
            expected = "Bearer " + token.get_secret_value()
            if not secrets.compare_digest(supplied.encode(), expected.encode()):
                raise HTTPException(
                    status_code=401,
                    detail="A valid management token is required.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        guarded(request)

    def record_answer(answer: InvestigationAnswer) -> None:
        provider = configuration.llm_provider
        answer_count.labels(answer.status, provider).inc()
        investigation_time.labels(provider).observe(max(0, answer.elapsed_ms) / 1000)
        if not answer.cached:
            for direction in ("input", "output"):
                llm_tokens.labels(direction, provider).inc(
                    max(0, answer.usage.get(f"{direction}_tokens", 0))
                )
            for step in answer.trace:
                stage = (
                    step.stage
                    if step.stage
                    in {
                        "planning",
                        "retrieval",
                        "follow_up",
                        "verification",
                        "generation",
                        "synthesis",
                        "tool",
                        "cache",
                    }
                    else "other"
                )
                stage_time.labels(stage).observe(max(0, step.duration_ms) / 1000)

    async def file_content(file: UploadFile) -> tuple[str, bytes]:
        try:
            content = await file.read(configuration.max_upload_mb * 1024 * 1024 + 1)
        finally:
            await file.close()
        if len(content) > configuration.max_upload_mb * 1024 * 1024:
            raise HTTPException(
                status_code=413, detail=f"Files must be at most {configuration.max_upload_mb} MB."
            )
        if not content:
            raise HTTPException(status_code=422, detail="The uploaded file is empty.")
        filename = (file.filename or "upload.txt").replace("\\", "/").rsplit("/", 1)[-1]
        if not filename or len(filename) > 240:
            raise HTTPException(status_code=422, detail="The filename is invalid or too long.")
        return filename, content

    @app.get("/health", tags=["operations"])
    def health(request: Request):
        return {
            "status": "ok",
            "boot_id": request.app.state.boot_id,
            "started_at": request.app.state.started_at,
        }

    @app.get("/ready", tags=["operations"])
    def ready(request: Request):
        if not request.app.state.ready:
            return JSONResponse(status_code=503, content={"status": "starting"})
        try:
            request.app.state.store.stats()
        except Exception:
            LOGGER.exception("Readiness database check failed")
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ready"}

    @app.get("/metrics", tags=["operations"], include_in_schema=False)
    def metrics():
        return Response(generate_latest(registry), media_type="text/plain; version=0.0.4")

    @app.get("/api/v1/status", tags=["operations"])
    def status(request: Request):
        return {
            "name": configuration.app_name,
            "provider": configuration.llm_provider,
            "model": configuration.llm_model
            if configuration.llm_provider != "extractive"
            else "extractive",
            "embedding_model": configuration.embedding_model,
            "retrieval_mode": configuration.retrieval_mode,
            "management_protected": bool(configuration.admin_token),
            "max_upload_mb": configuration.max_upload_mb,
            "corpus": request.app.state.store.stats(),
        }

    @app.get("/api/v1/documents", tags=["documents"])
    def documents(request: Request, limit: int = 50, offset: int = 0):
        if limit < 1 or limit > 100 or offset < 0:
            raise HTTPException(
                status_code=422, detail="limit must be 1–100 and offset non-negative."
            )
        docs = request.app.state.store.list_documents(limit=limit, offset=offset)
        return {
            "items": [doc.model_dump(exclude={"text", "blocks"}) for doc in docs],
            "limit": limit,
            "offset": offset,
        }

    @app.post(
        "/api/v1/documents",
        tags=["documents"],
        status_code=201,
        dependencies=[Depends(authorize_write)],
    )
    async def upload(request: Request, file: Annotated[UploadFile, File()]):
        filename, content = await file_content(file)
        result = await run_in_threadpool(request.app.state.ingestion.ingest, filename, content)
        return result

    @app.get("/api/v1/documents/{document_id}", tags=["documents"])
    def document(request: Request, document_id: str):
        result = request.app.state.store.get_document(document_id)
        if result is None or result.status == "deleted":
            raise HTTPException(status_code=404, detail="Document not found.")
        return result

    @app.put(
        "/api/v1/documents/{document_id}",
        tags=["documents"],
        dependencies=[Depends(authorize_write)],
    )
    async def replace(request: Request, document_id: str, file: Annotated[UploadFile, File()]):
        current = await run_in_threadpool(request.app.state.store.get_document, document_id)
        if current is None or current.status == "deleted":
            raise HTTPException(status_code=404, detail="Document not found.")
        filename, content = await file_content(file)
        return await run_in_threadpool(
            request.app.state.ingestion.ingest, filename, content, document_id=document_id
        )

    @app.delete(
        "/api/v1/documents/{document_id}",
        tags=["documents"],
        status_code=204,
        dependencies=[Depends(authorize_write)],
    )
    def delete(request: Request, document_id: str):
        if not request.app.state.store.delete_document(document_id):
            raise HTTPException(status_code=404, detail="Document not found.")
        return Response(status_code=204)

    @app.get("/api/v1/passages/{passage_id}", tags=["sources"])
    def passage(request: Request, passage_id: str):
        chunks = request.app.state.store.get_chunks([passage_id])
        if not chunks:
            raise HTTPException(status_code=404, detail="Passage not found or superseded.")
        return chunks[0]

    @app.get("/api/v1/jobs/{job_id}", tags=["documents"])
    def job(request: Request, job_id: str):
        result = request.app.state.store.get_job(job_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Ingestion job not found.")
        return result

    @app.post(
        "/api/v1/investigations",
        response_model=InvestigationAnswer,
        tags=["investigations"],
        dependencies=[Depends(guarded)],
    )
    def investigate(request: Request, payload: InvestigationRequest):
        answer = request.app.state.engine.investigate(payload)
        record_answer(answer)
        return answer

    @app.post(
        "/api/v1/investigations/stream", tags=["investigations"], dependencies=[Depends(guarded)]
    )
    def stream(request: Request, payload: InvestigationRequest):
        def events():
            try:
                for item in request.app.state.engine.stream(payload):
                    event = str(item.get("event", "progress"))
                    # Fragments are generated only here from an accepted final
                    # answer. Neither raw tokens nor engine-supplied fragments
                    # can bypass the complete-answer validation below.
                    if event in {"token", "answer_fragment"}:
                        continue
                    # A small allowlist prevents control characters in the SSE field.
                    if event not in {
                        "progress",
                        "stage",
                        "plan",
                        "retrieval",
                        "evidence",
                        "final",
                        "answer",
                        "result",
                        "error",
                    }:
                        event = "progress"
                    data = item.get("data", {})
                    if event in {"final", "answer", "result"}:
                        answer = InvestigationAnswer.model_validate(data)
                        record_answer(answer)
                        data = answer.model_dump(mode="json")
                        event = "final"
                        for offset in range(0, len(answer.answer), 120):
                            fragment = {"text": answer.answer[offset : offset + 120]}
                            yield (
                                "event: answer_fragment\ndata: "
                                + json.dumps(fragment, ensure_ascii=False)
                                + "\n\n"
                            )
                    yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            except EngineError as exc:
                yield f"event: error\ndata: {json.dumps({'code': exc.code, 'message': str(exc)})}\n\n"
            except Exception:
                LOGGER.exception(
                    "Streaming request failed; request_id=%s", request.state.request_id
                )
                yield 'event: error\ndata: {"code":"internal_error","message":"The investigation could not be completed."}\n\n'

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    templates = Jinja2Templates(directory=str(PACKAGE / "templates"))
    app.mount("/static", StaticFiles(directory=str(PACKAGE / "static")), name="static")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "app_name": configuration.app_name,
            },
        )

    return app

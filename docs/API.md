# HTTP API

Run `uvicorn investigation.web:create_app --factory --host 0.0.0.0 --port 8000`.
The same origin serves the workstation at `/` and interactive OpenAPI documentation
at `/docs`. All application API routes use `/api/v1`.

| Method and path | Input | Result |
| --- | --- | --- |
| `GET /status` | none | Public provider/model names, management protection flag, upload limit, corpus counts. No secrets. |
| `GET /documents` | `limit` (1–100, default 50), `offset` (default 0) | `{items, limit, offset}`. Summaries exclude full text and blocks. |
| `POST /documents` | multipart field `file` | `201` and an ingestion result: `created`, `duplicate`, `near_duplicate`, or `updated`, plus document, duplicate ID, warnings. |
| `GET /documents/{id}` | document ID | Current document revision including extracted text and source metadata. |
| `PUT /documents/{id}` | multipart field `file` | Replacement ingestion result; document ID is retained and revision advances on changed content. |
| `DELETE /documents/{id}` | document ID | `204`, or `404` for missing/deleted document. |
| `GET /passages/{id}` | passage ID | Stored passage, exact source location, document ID and revision. Missing or superseded passages return `404`. |
| `GET /jobs/{id}` | ingestion job ID | Durable batch job progress, or `404`. |
| `POST /investigations` | JSON investigation request | Validated answer, claims, citations, conflicts, plan, trace, model and usage metadata. |
| `POST /investigations/stream` | Same JSON | Server-sent progress, `answer_fragment` text events from the validated answer, then one structured `final` answer; failures use an `error` event. |

Example investigation request:

```json
{
  "question": "Which change caused the Atlas payment delay?",
  "filters": {"document_ids": [], "dataset": null, "source_type": null, "revision": null},
  "mode": "hybrid",
  "rerank": true,
  "use_cache": true
}
```

`mode`, `rerank`, and filters are optional. Questions must be 3–2000 characters.
The client should inspect answer `status`: `answered`, `insufficient_evidence`,
`conflicting_evidence`, or `error`. Citation IDs refer to entries in `citations`;
each entry contains a passage ID resolving through the passage endpoint.

SSE uses standard event blocks:

```text
event: progress
data: {"stage":"retrieval","detail":"Finding evidence"}

event: answer_fragment
data: {"text":"The validated answer is transported in bounded text fragments..."}

event: final
data: {"question":"...","status":"answered","answer":"...", ...}
```

Use `fetch()` with a POST request and parse `ReadableStream` events; native
`EventSource` cannot submit this JSON body. After the complete engine answer
passes server model validation, the server emits its answer text in fragments
of up to 120 characters, immediately followed by the structured final object.
The UI accumulates these fragments using `textContent` in a progress preview;
the final object replaces that preview with findings, claims and source cards.
This is verified-answer transport streaming, not provider-token streaming or an
improvement in time to first generated token. There are no artificial delays.
Raw provider token events and engine-supplied fragment events are never forwarded.
HTTP validation/auth/rate failures occur before the stream begins; errors after
headers are sent are represented by an SSE `error` event.

## Access and error handling

When `ADMIN_TOKEN` is configured, all document mutation routes require
`Authorization: Bearer <token>`. Production configuration requires that token.
Read/search routes are public: this is a public demonstration corpus, not a
private document vault. The UI states this before upload. Its management token
is kept only in the current browser tab's session storage and is never put in a
URL or embedded in server-rendered HTML.

Questions and document writes share a per-peer sliding-window rate limit.
Client-supplied forwarded headers are ignored. `429` responses include a
`Retry-After` header. This process-local limiter is suitable for the single
free-tier instance; a multi-instance deployment needs an external shared limit.
An upload boundary rejects unauthorized requests before multipart parsing. It
caps the full request body (including streamed/chunked bodies) at the file limit
plus 64 KiB of multipart overhead. The file handler separately reads at most the
exact configured file limit plus one byte before rejection. The parser validates
supported formats and contents.

Expected errors include `401` unauthorized writes, `404` missing resources,
`413` upload too large, `422` invalid input/document, `429` request/concurrency
limit, and `503` unavailable provider. Domain errors have an `error` object with
`code`, `message`, and `request_id`; framework input/auth errors have `detail`.
Unexpected errors return a generic message, not exception internals.

Every response has `X-Request-ID`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: same-origin`, and a restrictive content security policy. API
responses are not cached by the browser. Source text is inserted as text, not
HTML; external source links only accept HTTP(S).

Operational endpoints are outside the API prefix:

- `GET /health` is process liveness and returns `status`, a fresh `boot_id` UUID for this application lifespan, and UTC `started_at`. These nonsensitive fields let a deployment capture distinguish two application instances; a single healthy response does not prove restart persistence.
- `GET /ready` performs a database check and returns `503` until ready or if the database is unavailable.
- `GET /metrics` exposes Prometheus request counts and HTTP latency, completed investigation outcomes and end-to-end latency, stage latency, and consumed input/output tokens. Labels use bounded route templates, provider identifiers, statuses, and stage names, never user questions or source text. Cached responses do not count their original token usage again.

Structured HTTP logs contain method, route template, status, request ID and
duration, not prompts, uploaded contents, tokens or query strings.

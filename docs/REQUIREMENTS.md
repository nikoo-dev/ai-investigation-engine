# Assignment traceability and submission gates

This matrix maps the eight-page **Applied AI – AI Investigation Engine Task** to
the implementation, the checks that exercise it, and the evidence still needed
before final submission. It translates the supplied Georgian requirements; it
does not treat the document's example technologies as requirements to implement
every listed product.

The implementation and verification evidence are different things. A provider
adapter with mocked HTTP tests does not prove a successful live LLM investigation.
A dataset preparation command does not prove that 50,000 records are indexed.
A deployment configuration does not prove a public URL is running.

At this review, Gemini credentials and the user's hosting/database accounts have
not been verified. Live Gemini evaluation, the public demo, hosted restart
persistence remain explicit external submission gates. A candidate's manual answer
review is recommended preparation, not an extra assignment requirement.
Generated reports and the final delivery checklist must be used to update
the run-dependent entries below; do not infer completion from this matrix alone.

Measured local evidence is summarized in the [evaluation report](EVALUATION_REPORT.md):
50,085 reconciled source records, a 92-case full-corpus preview evaluation, five
controlled configuration comparisons, a full-corpus concurrency benchmark and
read-only browser verification. These runs use real semantic embeddings with
extractive answers; they do not establish live Gemini quality or hosted behavior.

## 1. Investigation objective

| Assignment requirement | Implementation | Evidence / acceptance gate |
| --- | --- | --- |
| Retrieve, analyze and connect facts across a large corpus | [`Engine._run`](../src/investigation/engine.py), [`Retriever.search`](../src/investigation/retrieval.py), Qdrant-backed source corpus | Multi-hop cases in [`cases.jsonl`](../data/evaluation/cases.jsonl); retain an actual 50,000-record run and provider evaluation. |
| Handle questions needing several sources and logical conclusions | Tool planner, bounded follow-up searches, evidence aggregation and structured synthesis in [`engine.py`](../src/investigation/engine.py) | [`test_engine.py`](../tests/test_engine.py) covers orchestration and evidence boundaries; real multi-source answer quality requires Gemini evaluation plus manual review. |
| Explain answers through identifiable supporting documents | Claim-level citations resolving to exact stored quotations and revisions | Exact quote/source checks in [`test_engine.py`](../tests/test_engine.py), [`test_evaluation.py`](../tests/test_evaluation.py); browser source inspector tested locally. |
| Report insufficient or conflicting information without invented facts | Structured answer statuses, citation validation, verification pass, conservative numeric conflict detection | Invalid citations, verifier rejection and numeric-conflict tests; real abstention/conflict metrics remain provider-dependent. |

## 2. Core requirements

### Document processing

| Assignment bullet | Implementation | Evidence / acceptance gate |
| --- | --- | --- |
| At least three file formats | PDF, DOCX, TXT and Markdown parsers in [`parsers.py`](../src/investigation/parsers.py) | [`test_ingestion.py`](../tests/test_ingestion.py); confirm PDF, DOCX and TXT uploads on the final public deployment. |
| Extract text and important metadata | `ParsedDocument`, `Document`, source blocks, page/section locations, filename, format, checksum and provenance | Parser and Unicode tests; inspect a stored document through the API. Scanned PDFs without text require OCR outside this version. |
| Chunk text | [`chunk_document`](../src/investigation/chunking.py) with model tokenizer offsets and retained source spans | [`test_chunking.py`](../tests/test_chunking.py) reconstructs exact source slices, checks token budgets and preserves tails. |
| Handle duplicated information | Normalized SHA-256 exact duplicate checks; near-duplicate similarity plus word overlap, retaining distinct evidence | Duplicate, repeated-identity and batch-count tests in [`test_ingestion.py`](../tests/test_ingestion.py). |
| Add new documents | `Ingestor.ingest`, `POST /api/v1/documents`, library upload form | HTTP lifecycle and actual runtime integration test in [`test_web.py`](../tests/test_web.py); desktop browser upload tested. |
| Update existing documents | Stable document ID, revision advancement, new chunks prepared before publication | Revision/failure/timeout tests in [`test_storage.py`](../tests/test_storage.py); browser replacement produced revision 2. |
| Delete documents | `Store.delete_document`, API delete and library action; source resolution rejects removed evidence | Storage and API lifecycle tests; browser deletion tested. |
| Compare at least two chunking strategies | `fixed` windows and `structure` grouping; isolated collection signatures prevent mixing | Two-strategy tests; run both on identical corpus/case manifests and retain measured comparison reports. |
| Select and justify processing architecture | Separate parser, chunker, embedding, ingestion and storage services | [`runtime.py`](../src/investigation/runtime.py) shows composition; README/architecture documentation must explain the tradeoffs. |

### Vector database and retrieval

| Assignment bullet | Implementation | Evidence / acceptance gate |
| --- | --- | --- |
| Use a vector database or vector-capable database | [`Store`](../src/investigation/storage.py), Qdrant with named dense/sparse vectors and durable metadata collections | Local persistence and collection compatibility tests; remote Cloud integration must be verified after account setup. |
| Use embeddings and semantic search | FastEmbed ONNX `DenseEmbedder`; cosine search in Qdrant | Real-model corpus ingestion/search evidence is required. `HashEmbedder` is an offline test double and does not satisfy this requirement. |
| Implement hybrid semantic plus keyword search | Dense retrieval and BM25-style sparse retrieval with Qdrant IDF modifier | [`Retriever.search`](../src/investigation/retrieval.py); compare dense-only and hybrid results under the same corpus/cases. |
| Implement at least one custom algorithmic search/ranking component | Weighted reciprocal rank fusion, subquestion coverage reward, duplicate-content removal and soft document diversity | Formula and deterministic behavior tested in [`test_retrieval.py`](../tests/test_retrieval.py). This code is implemented directly rather than delegated to a RAG framework. |
| Do not rely on ordinary SQL text search alone | Qdrant dense vectors participate in `dense`/`hybrid` modes | Confirm submitted configuration is real FastEmbed + hybrid mode; sparse-only is an experimental comparison. |
| Technology choice is open | Qdrant is the selected alternative | Pinecone, Neon/pgvector, Supabase, Weaviate and Chroma are permitted examples, not additional required integrations. |

### LLM integration and RAG

| Assignment bullet | Implementation | Evidence / acceptance gate |
| --- | --- | --- |
| At least one LLM | Gemini REST adapter; optional Ollama adapter in [`llm.py`](../src/investigation/llm.py) | Native-call HTTP tests pass with mocked transports; a real configured provider run is still required. |
| RAG architecture | Plan → retrieve tools → evidence aggregation → structured synthesis → verification → cited answer | Same pipeline serves UI and CLI through [`Runtime`](../src/investigation/runtime.py). |
| Combine information from different documents | Multiple focused searches and a merged evidence context with document identity | Multi-source fixture gold labels; measure all-support retrieval and inspect final claims manually. |
| Process difficult questions in several steps | `propose_tools`, optional `follow_up`, `synthesize`, `verify` | [`test_llm.py`](../tests/test_llm.py) verifies follow-up receives tool evidence; live multi-hop evaluation remains necessary. |
| Generate evidence-grounded answers | Structured claims require evidence references; final prose is rendered from accepted claims | Fabricated/mismatching source tests reject unsupported drafts. Exact quoting alone is not proof of entailment. |
| Source and citation mechanism | `Citation` includes document, passage, revision, location and exact quote | Source-resolution evaluation and browser inspector checks; public sources must remain resolvable. |
| Attempt contradiction detection | LLM synthesis/verifier status plus conservative numeric disagreement checks keyed by subject/entity/date | Numeric regression tests and dedicated contradictory questions; report false positives and missed conflicts. |
| Abstain when information is insufficient | `insufficient_evidence` on absent evidence, invalid source references, rejected verification or changed sources | Engine tests; unanswerable evaluation category with explicit denominator. |
| Handle LLM communication errors and limits | Bounded retries, capped backoff, timeout, rate-limit handling, invalid JSON and blocked/truncated response rejection | [`test_llm.py`](../tests/test_llm.py); no silent fallback from failed Gemini calls to successful extractive answers. |
| At least one tool-calling or equivalent structured tool invocation | Allowlisted `search_documents`, `fetch_passages`, `inspect_document` schemas; server-side argument validation and budgets | Native Gemini tool round-trip and scope/budget tests. Tool functions cannot mutate documents or execute arbitrary code. |
| Model, prompts and framework are free choices | Explicit prompts and small HTTP adapter, Pydantic models, no opaque agent framework | Explain model choice and prompt boundaries during defense; final model access/quota must be checked. |

### Automated evaluation

| Assignment bullet | Implementation | Evidence / acceptance gate |
| --- | --- | --- |
| Create a custom automated evaluation system | [`evaluate`](../src/investigation/evaluation.py), `score_case`, machine-readable results and generated Markdown | Metric, failure-denominator and manifest-comparison tests in [`test_evaluation.py`](../tests/test_evaluation.py). |
| At least 40 test questions | Committed fixture: 88 total, including 72 test, 12 tuning and 4 security cases | [`manifest.json`](../data/evaluation/manifest.json) contains category counts and checksums. |
| Simple and multi-step questions | Direct, comparison and multi-hop categories | 72 test cases include 12 direct, 12 comparison and 24 multi-hop questions. |
| Questions linking several documents | Gold document IDs and required hops per multi-hop case | Fixture validation rejects missing labels; report all-support@10. |
| Questions absent from the data | 12 test unanswerable cases, separate from answerable cases | Report abstention accuracy, not retrieval credit for an empty gold set. |
| Questions with contradictory evidence | 12 test contradiction cases using distinct audit exports | Report conflict status and explanation; inspect both quotations. |
| Quantify retrieval quality | Recall@5/10, MRR, all-support@10, evidence precision@10 | Formulas and denominators documented in [`EVALUATION_METHODOLOGY.md`](EVALUATION_METHODOLOGY.md). |
| Quantify answer quality | Lexical token F1/exact match, required-fact recall, citation source validity, gold citation coverage, abstention/conflict outcomes | These metrics are proxies; inspect semantic correctness and claim entailment separately. Optional disclosed manual/model review can help. |
| Compare at least two configurations | CLI `evaluate` and `compare`; collection signatures isolate chunking/model changes | Retain actual fixed/structure and dense/hybrid reports with identical case-manifest hashes. |
| Analyze where, why and how the system fails | Per-case predictions, trace, source labels, error types and report breakdowns | Final evaluation report must discuss actual failures and improvements, including any test-set-driven changes. |

### Backend and interface

| Assignment bullet | Implementation | Evidence / acceptance gate |
| --- | --- | --- |
| Python backend | FastAPI app factory in [`web.py`](../src/investigation/web.py) | API tests use injected services and real local runtime. |
| Functional UI | Server-rendered shell with local JavaScript/CSS | Desktop/mobile browser verification, no external CDN dependency. |
| Add/manage documents, ask questions, inspect sources | Library lifecycle controls, investigation form, source dialog, progress and trace | [`API.md`](API.md), HTTP lifecycle tests and actual browser workflows. |
| Define API structure and architecture | Versioned typed REST endpoints and SSE transport | OpenAPI `/docs`; [API contracts](API.md); shared [`models.py`](../src/investigation/models.py). |
| Prioritize function, reliability and code quality | Error/empty/loading states, safe text rendering, upload limits, protected writes and regression checks | Security and browser tests; avoid equating polished screenshots with answer quality. |

## 3. Dataset

| Assignment bullet | Implementation | Evidence / acceptance gate |
| --- | --- | --- |
| Use one or more supplied dataset options | Pinned official `hotpotqa/hotpot_qa` revision in [`datasets.py`](../src/investigation/datasets.py) | Preparation downloads immutable parquet files, records hashes and attribution; no arbitrary remote loading script. |
| At least 50,000 documents or independent text records | Deterministic unique source-passage subset; authored fixture is supplementary | `investigate status` must show at least 50,000 active documents after ingestion. Reconcile manifest IDs and ingestion failures, not QA/chunk counts. |
| Find related information across documents | HotpotQA supporting-fact provenance plus authored incident/change/verification/ownership records | Held-out evidence labels remain outside the index. |
| Preserve and identify sources | Stable UUIDs, source titles/URIs, record IDs, source sentences and content checksums | Dataset provenance tests, stored source inspect, citation resolution. |
| Handle incomplete/conflicting information | Independent unanswerable and audit-conflict cases | Report decisions by category and manually check source relevance. |
| Repeatable evaluation | Frozen seed, revision, manifest and case hashes | Byte-reproducible seed generation and incompatible-comparison rejection tests. |
| Reproducible subset is allowed if full dataset is large | `prepare-dataset --records 50000 --seed 42` | Preserve generated manifest and explain subset selection. |
| Additional public/synthetic records are allowed | Authored incident fixture explicitly labeled synthetic/CC0 | Do not describe synthetic incident reports as real operational incidents. Other listed datasets are alternatives, not required additions. |

## 4. Free hosting and deployment

| Assignment bullet | Implementation / selected approach | Required external evidence |
| --- | --- | --- |
| Real public application URL | Containerized FastAPI/UI on Render free web service | **Pending accounts/deployment:** record a reachable HTTPS URL and smoke-test it from outside the development machine. |
| Working host/database integration | Remote Qdrant Cloud; production requires `QDRANT_URL` | Upload, query, citation, update and delete on the hosted app using the actual remote store. |
| Data survives application restart | Durable documents/chunks/jobs/state in Qdrant; local caches may be rebuilt | Local restart test exists. Restart/redeploy the hosted application and repeat source/count checks. |
| Protect API keys and secrets | Environment/secret settings, `SecretStr`, management bearer token, generic provider errors | Secret-safe HTTP tests; verify repository history and deployed client assets contain no credentials. |
| Describe deployment architecture | One application container and external persistent Qdrant; browser only contacts the app | README/deployment guide must include the public URL, environment setup and persistence boundaries. |
| Account for cost, resources and free-tier limits | Local CPU embeddings, bounded provider calls/context, caching, request/concurrency limits | Record actual account quotas, model availability, host memory and cold starts before submission. |
| No paid infrastructure required | Select free hosting/database tiers and a free-access model allowance | Verify current account eligibility; do not enable paid plans or assume quota availability. |
| Sleeping/request limits are acceptable when documented | UI connection/loading errors and deployment operating notes | Demonstrate that cold start and free limits do not prevent the core demo. |

## 5. Technical quality

| Assignment bullet | Implementation | Evidence / acceptance gate |
| --- | --- | --- |
| Understandable modular Python | Focused parser/chunker/embedding/storage/retrieval/LLM/engine/API/evaluation modules | Walk through the composition root and individual modules without AI assistance. |
| Separation of responsibilities | Typed contracts and dependency injection; transport outside orchestration | Runtime factory and isolated fake-provider/API tests. |
| Error handling | Domain errors, safe HTTP responses, typed provider failures, upload/parse validation | Invalid inputs, retry, timeout, safety block and partial-update tests. |
| Automated tests | [`tests/`](../tests) and [`Verify` CI workflow](../.github/workflows/ci.yml) | Run pytest, Ruff, format check, mypy, build and container checks; retain actual outputs. A workflow file alone is not a green hosted run. |
| Correct database/external API integration | Qdrant adapters and explicit Gemini tool protocol | Local integration and mocked HTTP tests; live Cloud/Gemini checks still required. |
| Secure environment configuration | Validated [`Settings`](../src/investigation/config.py), ignored `.env`, example configuration, production guards | Config tests plus manual deployed-secret configuration; never paste actual keys into reports. |
| Technical documentation | README, API, methodology, requirement matrix, interview guide, demo script and disclosure | Check every documented command on a clean environment. |
| Understand performance and LLM cost | Timing traces, usage counters, caches, benchmark CLI, Prometheus metrics | Retain actual latency/memory/token reports. Never report extractive runs as paid/free LLM cost evidence. |

## 6. Bonus items

| Bonus bullet | Implementation | Honest completion boundary |
| --- | --- | --- |
| Compare multiple LLMs or embedding models | Configurable `EMBEDDING_MODEL`, dimension and collection prefix; Gemini/Ollama provider interface | **Run-dependent:** retain a second real model experiment on identical cases. Adapter availability alone is not a comparison. |
| Multi-agent or agentic RAG | Bounded planner/tool retrieval/follow-up/synthesis/verifier stages | Agentic workflow is implemented. It does not claim independent autonomous agents or independent model truth. |
| More advanced reranking | ONNX cross-encoder in `Reranker` after fusion | Test ordering and actual on/off quality/latency comparison; account for CPU/RAM cost. |
| Prompt injection resistance testing | Untrusted-evidence policy, allowlisted non-mutating tools, argument scope checks, safe browser rendering, four security cases | Regression tests plus a real-provider security run; regex checks alone do not prove immunity to prompt injection. |
| Caching and performance optimization | Fingerprinted embedding cache; bounded retrieval and answer caches keyed by corpus revision | Cache invalidation/delete tests. Embedding cache is recomputable local storage, not the authoritative document store. |
| Streaming answers | SSE stage events, text fragments from the validated answer, then its structured final object | Verified-answer transport streaming works; it does not reduce provider generation latency. |
| Detailed monitoring/observability | Request IDs, structured request logs, per-answer trace/usage, Prometheus HTTP/outcome/stage/latency/token metrics | Local metric tests; production metrics reset per process and no hosted tracing service is claimed. |
| Large-data performance testing | `run_benchmark` and `run_ingestion_benchmark` record actual corpus count, latency, throughput and sampled RSS | **Run-dependent:** attach a measured run with 50,000+ active documents. Small fixture timing is not scale evidence. |

Bonus work does not waive any core requirement.

## 7. Submission artifacts

| Required deliverable | What must be supplied |
| --- | --- |
| GitHub repository, full code and history | Publish the reviewed code and meaningful commit history to the user's repository. A local `.git` directory is not the required GitHub URL. |
| Live demo | A publicly reachable hosted application, with a tested cold-start path and working persistent corpus. **Pending external account setup.** |
| README | Purpose, architecture, setup, configuration, usage, evaluation, deployment, choices and limitations; link all reports and the actual demo. |
| Evaluation report | Generated results, exact configurations/manifest hashes, methodology, comparison and failure analysis. Disclose any optional manual/model review. **Real Gemini evaluation pending key.** |
| AI Usage Report | [`AI_USAGE_REPORT.md`](AI_USAGE_REPORT.md), describing actual AI assistance and clearly separating it from the candidate's own verified work. |

## 8. Interview and code defense

| Assignment bullet | Preparation and acceptance |
| --- | --- |
| Explain the architecture | Use [`INTERVIEW_GUIDE.md`](INTERVIEW_GUIDE.md) and trace a request through real code. |
| Discuss a specific code section in detail | Explain and calculate custom fusion, source offsets or revision publication without reading a generated script. |
| Describe RAG step by step | Demonstrate plan, tools, retrieval, evidence budget, synthesis, validation, abstention and citations. |
| Find and fix a code error | Complete the guide's debugging exercises and run the relevant tests without AI. |
| Add/change functionality live | Practice a small typed API/filter or ranking change and its tests without AI. |
| Justify algorithms and decisions | Explain alternatives, complexity, failure modes and measured tradeoffs rather than repeating architecture labels. |
| No AI assistants in practical interview | The candidate must practice with assistants disabled. This repository/report does not assert that this independent preparation has already happened. |

Final submission is ready only when the public URL, real LLM evaluation, required
scale and comparisons, generated artifacts, and independent code-defense
preparation are supported by actual evidence.

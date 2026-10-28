# Code defense and independent practice

The practical interview prohibits AI assistants. This guide is preparation
material, not evidence that the candidate has already completed the exercises.
Before the interview, disable assistants and practice navigating, explaining,
debugging and changing the repository independently. Be explicit about the AI
assistance disclosed in [the usage report](AI_USAGE_REPORT.md).

## Explain the project in 90 seconds

The application investigates a question using an indexed corpus of attributable
source passages. Python services parse documents and retain text locations, split
them within the embedding model's token budget, and persist dense/sparse vectors
and document revision state in Qdrant. A question triggers focused tool searches.
The application fuses semantic and keyword ranks, optionally reranks candidates,
then asks the language model for claims and exact supporting quotations. Server
validation resolves those quotations and a second model call checks support.
The answer can report insufficient evidence or conflicting sources. The UI makes
the sources inspectable, and the evaluator records retrieval, citation, answer
diagnostic, latency and failure metrics.

Avoid saying that a second model call proves truth. It is a check by the same
provider/model, not an independent authority. Exact quotations prove the source
text exists; they do not by themselves prove that a claim follows from it.

Start a code walkthrough at [`build_runtime`](../src/investigation/runtime.py).
It constructs the embedder, store, ingestor and engine used by both the CLI and
web application. Then follow [`create_app`](../src/investigation/web.py),
[`Engine.stream`](../src/investigation/engine.py),
[`Retriever.search`](../src/investigation/retrieval.py), and
[`LLMClient`](../src/investigation/llm.py).

## Trace one document into an answer

1. The HTTP upload boundary checks management authorization and bounds the body
   before multipart parsing. The file reader applies the exact file-size limit.
2. `parse_document` selects PDF, DOCX or UTF-8 text parsing, validates the content,
   and builds source blocks. PDF page numbers and DOCX section/table structure
   become metadata; extracted text offsets are relative to normalized stored text.
3. `Ingestor.ingest` calculates a normalized content checksum. Identical content
   reuses its existing source; a similar but different document is retained.
4. `Ingestor._chunks` supplies the production embedding tokenizer's offsets to
   `chunk_document`, reserving model capacity for title text. Oversized structure
   blocks use overlapping windows. No model-truncated source tail should vanish.
5. `DenseEmbedder` produces normalized ONNX vectors. `SparseMixin.sparse` computes
   deterministic BM25-style term weights; Qdrant supplies corpus-dependent IDF.
6. `Store.commit_document` writes candidate chunks, publishes the document marker,
   then removes the old revision. Search and source resolution check the current
   ready document revision before returning a passage.
7. A question becomes an `InvestigationRequest`. `Engine._run` obtains the corpus
   revision and a bounded investigation slot, plans tool calls, retrieves evidence
   and may run a focused follow-up for a missing link.
8. The LLM produces a structured `AnswerDraft`. `_validate_draft` accepts only
   references to supplied passage IDs and exact quote substrings. The verifier can
   reject unsupported claims, incomplete answers or unresolved conflicts.
9. `_render` builds the final text from accepted claims/conflicts. `Citation`
   includes the source document, passage, revision, location and quote.
10. The browser receives progress, validated answer text fragments, then the final object. Opening
    a citation fetches the stored passage. Evaluation can independently resolve
    that same passage and compare the answer to gold labels.

Be able to repeat this sequence while opening the actual functions and explaining
their parameters, returned models and failure paths.

## Explain the custom retrieval algorithm

Raw cosine scores and lexical scores have different ranges and meanings. The
custom `reciprocal_rank_fusion` combines positions instead:

```text
score(passage) = sum(weight[channel] / (60 + rank[channel, passage]))
```

Missing passages contribute zero, and a duplicate passage in one ranking
contributes only once. With equal weights, passage A at dense rank 1 and sparse
rank 3 scores `1/61 + 1/63 ≈ 0.032266`; B at ranks 2 and 1 scores
`1/62 + 1/61 ≈ 0.032522`, so B wins. Stable ID ordering breaks exact ties.
The implementation merges channel provenance and rewards coverage across
subquestions with a small multiplier. `diversify` greedily applies a soft penalty
for repeated documents and removes exact duplicate chunk content.

Explain why diversity is soft: a hard one-passage-per-document cap could discard
two necessary facts from one source. Explain the tradeoff in `k=60`: rank fusion
is robust to score scale but loses information about absolute score separation.
It is not a calibrated probability of relevance or correctness.

The cross-encoder sees the question and passage together, so it can distinguish
closely related candidates more precisely than independent dense embeddings.
Its CPU cost grows with candidate count and passage length. That is why it is
applied to a bounded candidate set. Inspect
[`test_retrieval.py`](../tests/test_retrieval.py) and compute an example by hand.

Sparse weights use term frequency and length normalization; IDF lives in Qdrant
because new documents change term rarity. The tokenizer's stopword handling and
configured average length must be considered when comparing lexical quality.
Do not describe hashed sparse token IDs as semantic embeddings. The separate
`HashEmbedder` is only a deterministic fixture for offline tests.

## Explain evidence, revisions and failure handling

| Interview question | What the code actually does and what remains a limitation |
| --- | --- |
| What if an update fails after some vectors are written? | The old document revision remains the visibility marker. Candidate hits are checked against that marker. Cleanup must not delete a new revision when a timeout occurred after publication; there is a regression test for this ambiguity. |
| Is publication a distributed transaction? | No. It is ordered publication with visibility checks and recovery behavior. A multi-writer production service would need stronger concurrency control; the demo uses one application writer. |
| What if a cited document is deleted during generation? | The engine rechecks source availability when the corpus revision changes and withholds stale citations rather than publishing an answer that cannot be inspected. |
| How are caches invalidated? | Keys include corpus revision and relevant configuration. Changing a source changes the revision. Embedding cache identity also includes the model fingerprint and input text. |
| Why not deduplicate near-identical reports automatically? | A changed date, negation or number may be the important evidence. Similarity only flags a possible duplicate; distinct text remains searchable. |
| Can two numbers prove contradiction? | No. The conservative numeric detector requires matching subject, entity and date. General semantic contradictions are attempted by the LLM workflow and can still be missed. |
| Is the first incident report enough to assert cause? | Not in the fixture: it records correlation. The change log plus later rollback/replay verification establish the intended chain. Inspect the actual source text. |
| What if Gemini returns malformed JSON, a rate limit or an incomplete answer? | The adapter validates response envelopes and structured models, retries only bounded transient errors, caps delay, rejects blocked/truncated output and raises a safe typed error. |
| Why simplify the provider JSON schema? | The live API rejected nested count/length constraints. The wire schema keeps structure/types/enums; the original Pydantic model still checks every local bound before exact citations and semantic verification. |
| Does the app silently switch providers? | No. Extractive mode is an explicit source-preview configuration; it is labeled and cannot stand in for the real LLM requirement. |
| What if a document says “ignore your instructions”? | Source/tool output is treated as untrusted evidence. Tool names/arguments are allowlisted, reads remain within discovered scope, document tools cannot delete data, and browser text is not interpreted as HTML. This reduces attack surface but does not prove universal injection resistance. |
| What exactly is streamed? | Stage progress, text fragments from the validated answer, then the structured final object. Provider generation completes before answer fragments are sent. |

Important tests to locate independently:

- `test_failed_replacement_keeps_previous_revision` and
  `test_publication_timeout_does_not_destroy_committed_revision` in
  [`test_storage.py`](../tests/test_storage.py).
- `test_invalid_citation_or_verifier_rejection_withholds_model_answer`,
  `test_source_deleted_during_generation_cannot_publish_stale_citation` and
  `test_unknown_tools_and_extra_filters_cannot_escape_user_scope` in
  [`test_engine.py`](../tests/test_engine.py).
- Native tool round-trip, secret-safe errors, retry limits and truncated outputs
  in [`test_llm.py`](../tests/test_llm.py).

## Defend the evaluation

Read [the methodology](EVALUATION_METHODOLOGY.md) and one complete results row,
not only an aggregate table. Know the distinction between retrieval gold labels,
answer references, required facts and source-quote validity.

Recall@K asks how many required source documents were found. MRR only rewards the
first relevant result, so it can look good while the second reasoning hop is
missing. All-support@10 is stricter for multi-hop questions. Citation source
validity asks whether an exact source reference exists; citation gold precision
asks whether the source document is labeled relevant. Neither is full entailment.

Token F1/exact match measure lexical agreement, not semantic correctness. A
longer correct answer may have lower F1, and a wrong claim containing expected
words can have high fact recall. Disclose manual review of claims and supporting
passages rather than claiming an unimplemented semantic judge. Unanswerable
questions do not receive perfect retrieval scores merely because their gold set
is empty. Provider errors stay in metric denominators.

The authored fixture contains 85 source documents and 88 cases: 72 test, 12 tuning
and 4 security. The two tuning incidents are separated from the test incidents.
The HotpotQA subset uses a pinned revision and deterministic seed; question and
answer labels are not indexed as source text. A source record is an independent
passage, not a chunk or duplicated QA row. The final 50,000-record proof must use
active stored document counts and ID reconciliation after ingestion.

When comparing chunking or embedding models, use a separate collection prefix;
the stored signatures intentionally reject incompatible mixing. Run the same
cases and corpus, keep the manifest hash, and report retrieval quality, answer
diagnostics, source accuracy, failures and latency together. If you tune after
seeing test failures, disclose it and obtain fresh held-out cases before making
an unbiased improvement claim.

## Defend deployment and operating limits

The browser calls the FastAPI service, not Gemini or Qdrant directly. Secrets
remain server-side. The public demo corpus is intentionally readable; management
writes require a bearer token in production. It is not a private tenant vault.

Durable documents, chunks, job metadata and corpus state live in Qdrant. The
application host's embedding/model caches are recomputable. A free host restart
must not erase source data. Embedded local Qdrant is for one process; use the
server/Cloud endpoint for shared access and hosted deployment. Local-client
exact-scan performance is not evidence of hosted HNSW performance.

For intuition, 50,000 vectors × 384 dimensions × 4 bytes is about 76.8 MB of raw
dense values, before payloads, sparse indexes, graph structures and duplicate
document/chunk text. Real memory and disk use must be measured. The model and
cross-encoder also consume memory; free CPU hosting has limits. Per-process
metrics/rate limits reset on restart and are not a distributed observability or
quota system. Be ready to explain a cold start, a provider `429`, a database
outage and the difference between `/health` and `/ready`.

## Practice without AI

Use a disposable collection prefix and the small authored fixture. Stop a local
web process before opening the same embedded Qdrant directory from another CLI
process. Never practice destructive changes against the submission corpus.

1. **Calculate and change ranking.** Predict the order for three passages in two
   rankings. Change channel weights or the diversity penalty, add an assertion
   covering the intended behavior, and explain the tradeoff. Run
   `uv run pytest tests/test_retrieval.py`.
2. **Diagnose a missed reasoning hop.** Inspect a failed case's retrieved IDs and
   gold sources. Determine whether parsing, chunking, first-hop retrieval,
   follow-up query or context selection lost the evidence. Do not immediately
   increase every limit.
3. **Add a safe metadata filter.** Add a typed field to `SearchFilters`, translate
   it in `Store._filter`, and verify both dense and sparse channels honor it.
   Check tool calls cannot override the user's scope.
4. **Fix a stale-cache bug.** Temporarily remove corpus revision from a cache key
   in a disposable branch. Reproduce a stale result after update/delete, restore
   the correct invalidation and run the relevant regression test.
5. **Investigate unsupported output.** Use a fake draft with a wrong passage ID or
   one changed word in a quotation. Explain why the server rejects it. Then use
   an exact quote that does not support the claim to explain why a verifier and
   manual entailment review are still necessary.
6. **Add a parser feature.** Add one small behavior, such as retaining a Markdown
   heading level in metadata. Preserve exact source offsets and test it without
   breaking the three required formats.
7. **Handle a provider failure.** Read the HTTP adapter, explain when it retries
   and when it refuses, and add a test for a realistic malformed response without
   printing a secret-bearing body.
8. **Explain and extend an endpoint.** Add a harmless typed document-summary
   field or list filter, update OpenAPI/API docs and one meaningful route test.
   Confirm public reads and protected writes keep their intended boundaries.

Run the project checks after the change:

```text
uv run ruff check .
uv run ruff format --check .
uv run mypy src/investigation
uv run pytest
```

For every exercise, explain the previous behavior, your change, its failure
cases, the evidence from the test, and what you would measure before rollout.
Do not claim independent mastery until you can do that without an assistant.

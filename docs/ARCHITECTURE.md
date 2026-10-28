# Architecture and design decisions

## Data and publication

Four Qdrant collections hold passages, document publication rows, jobs, and corpus
metadata. Passages have named `dense` and `sparse` vectors; the other collections
are payload-only. A document contains normalized text, structural blocks, source
locations, checksum, metadata, revision, and lifecycle state. A chunk's stable UUID
includes document ID, revision, strategy, character span, and text checksum.

The write sequence is index new chunks -> publish document revision -> remove old
chunks. Queries verify each candidate against the active document revision. Failed
indexing leaves the old revision visible. Publication failures never authorize
deleting a new revision that may already have been committed. A deletion first
tombstones the document, wipes its source payload, and then removes chunks. These
operations are not a distributed database transaction; active-revision checks are
the visibility boundary. One writer process is recommended for a demonstration.

The corpus-generation UUID changes after writes and is part of every cache key.
If a source is replaced/deleted mid-investigation, citation passages are rechecked
before publishing. Caches contain copies and cannot mutate stored search results.
All durable state lives in Qdrant; the local SQLite embedding cache is expendable.

## Parsing and chunking

PDF parsing preserves page locations. DOCX preserves paragraphs/headings. Plain
text/Markdown preserves paragraphs. Parsers bound upload and extracted-text sizes,
reject empty/corrupt/encrypted/unsupported documents, and guard DOCX archive sizes.
Exact duplicates normalize Unicode/whitespace/case before hashing. Similar uploads
are flagged but kept, because one changed number or negation may be the critical
evidence. Batch corpus imports deduplicate exact content without an O(N²) scan.

Fixed windows overlap by a configurable token count. Structural chunks group
paragraphs/sentences within their page/section and split oversized blocks. Dense
ingestion uses the actual ONNX model tokenizer, with truncation disabled on a
separate tokenizer copy, to calculate character spans. The title prefix consumes
part of the model's context budget; the body must fit the remainder. Every
embedding input is checked before inference so a cited tail cannot disappear
silently from its vector representation. Test doubles use deterministic Unicode
word/punctuation tokenization instead.

Collection signatures bind model identity, dimensions, chunk configuration, BM25
average length, and ingestion pipeline version. Incompatible experiments use a
different collection prefix; they never overwrite an existing index in place.

## Hybrid ranking: custom algorithm

Dense cosine and BM25 scores have different scales. Rank fusion uses:

`RRF(p) = sum_channel weight[channel] / (60 + rank_channel(p))`

Each passage contributes once per ranking. Ties are broken by stable passage ID.
When rankings cover separate subquestions, a passage receives a bounded coverage
bonus of `1 + 0.08 * (covered_subquestions - 1)`. Greedy selection divides each
candidate's score by `1 + 0.2 * already_selected_from_document`, suppressing repeats
without a hard document cap that might discard necessary evidence. Exact duplicate
chunk checksums are removed. The cross-encoder, when enabled, scores the top
candidate passages against the query before final selection.

The sparse encoder hashes normalized Unicode terms into 32-bit IDs and computes
`tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / average_length))`. Query weights are
one per term. Qdrant's `IDF` modifier supplies corpus rarity. Hash collisions are
rare but possible; colliding weights are summed consistently. English stopword
removal is explicit. Average length is configurable and must be measured/tuned
without reading final test answers. This is not a claim of full linguistic BM25
equivalence to a stemmed Lucene implementation.

## Investigation flow and safeguards

1. Validate the question, filters, provider configuration, and concurrency budget.
2. Ask the LLM for native corpus tool calls. All arguments are schema-validated.
3. Search each evidence need with dense/sparse retrieval and custom ranking.
4. For complex queries, ask whether the retrieved facts expose a missing bridge;
   execute a bounded second tool round. Fetch/inspect may only expand already
   discovered sources under the original filters.
5. Fuse subquestion rankings, select a bounded evidence context, and request a
   structured draft. It contains claims, exact passage references, and conflicts.
6. Resolve every source ID and quotation against active retrieved passages. Invalid
   citations withhold the answer rather than appearing as decorative links.
7. Run a separate LLM evidence-verification pass for proposed answers. Rejected
   claims or a missing reasoning link produce abstention.
8. Publish a typed answer, conflict, abstention, or explicit provider error, with
   citations, usage, elapsed time, and an inspectable trace.

Gemini's REST structured-output request uses `responseFormat.text`. The adapter
resolves local schema references and omits nested string-length/array-count
constraints from the decoder schema after the full bounded schema was rejected
by the live service. Types, required fields, enums and numeric ranges remain on
the wire; the original Pydantic model then enforces all local bounds before the
engine accepts a draft. This is separate from exact quotation and entailment
checks. See [Google's REST schema documentation](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
and the retained initial failed run in `reports/evaluation/gemini-full-hybrid/`.

The deterministic conflict detector requires matching subject/entity and explicit
date before treating different numeric assertions as disagreement. LLM synthesis
also attempts broader semantic conflicts. Neither approach guarantees complete
contradiction detection. A real measured conflict score remains essential.

Documents are untrusted data. They cannot select tools, change filters, access
environment variables, execute code, or cause network fetches. Only the trusted
provider adapter communicates externally. Model HTTP errors never expose response
bodies or API keys. Production management uses constant-time token comparison;
upload limits apply before multipart processing, and browser output uses text nodes.

## Reliability, observations, and costs

One app instance has bounded concurrent investigations, a bounded per-peer request
limiter, LRU retrieval/answer caches, model timeouts, bounded exponential retries,
and input/context/output limits. A complex Gemini query generally requires planning,
optional follow-up, synthesis, and verification calls. Input/output token counts
and retry counts are preserved; quota failures remain failures in evaluation.

Metrics cover HTTP method/route/status, request duration, answer outcome, full
investigation duration, stage duration, and model input/output tokens. Request IDs
connect application logs to a request. The trace exposes retrieval operations and
decisions without credentials. `/health` checks process availability; `/ready`
checks the storage dependency; `/metrics` uses Prometheus exposition.

An ONNX model still consumes RAM even when inference runs on CPU. Batch ingestion
belongs off the small web instance. Benchmark remote-Qdrant query memory and p95
latency on the chosen free host, lower candidate/reranker batch sizes if needed,
and do not infer cloud performance from embedded-Qdrant exact scans.

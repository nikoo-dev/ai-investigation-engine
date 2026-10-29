# Measured evaluation and remaining evidence

Reviewed on 2026-10-29. The measurements below were recorded on 2026-10-27;
their original timestamps and individual predictions remain in the linked files.
The completed local measurements below use real ONNX retrieval and extractive
preview. On 2026-10-29 the public Render/Gemini application and its Qdrant Cloud
corpus were verified. **The live LLM evaluation and matching configuration
comparisons remain incomplete.** Preview scores and partial live runs do not
substitute for final LLM evaluation evidence.

The initial corrected live run stopped after 53 recorded cases, including one
provider-output error. Its verifier explanations also revealed a decision-schema
ambiguity: explanations acknowledged conflicts while parsed decision flags were
false. That run remains unchanged in `reports/evaluation/gemini-full-hybrid-v2/`.
Decision flags are now mandatory, with explicit conflict semantics. The separate
[12-case tuning run](../reports/evaluation/gemini-tuning-v3/report.md) completed
with zero runtime errors, 100% expected-status accuracy, and both tuning conflicts
confirmed. These are tuning diagnostics, not held-out semantic-correctness claims.
The subsequent `gemini-full-hybrid-v3` run stopped after 45 cases when a model
conflict object failed the required two-sided evidence constraint. Those outputs
also remain unchanged. Minimum evidence counts are now included in the provider
schema as well as local validation.

The cloud run `reports/evaluation/gemini-cloud-hybrid-v4/` has 25 of 92 planned
test cases, including one provider error. Actual provider diagnostics identify
the project's **500 requests/day/model** free quota for `gemini-3.5-flash-lite`,
not a missing credential or a failed Render deployment. The
[quota diagnostic](../reports/deployment/gemini-daily-quota.json) retains the
actual quota ID and retry delay without credentials. All attempts remain in
the checkpoint. A separate free-model compatibility/tuning check uses Gemini
3.1 Flash-Lite; its results cannot be merged into the 3.5 run. That separate
[12-case tuning run](../reports/evaluation/gemini-3.1-tuning/report.md) completed
with zero runtime errors, all expected statuses correct, both conflicts surfaced
and both unanswerable cases withheld. Tuning diagnostics do not establish
held-out semantic accuracy. The new full-cloud run is
`reports/evaluation/gemini-3.1-cloud-hybrid/`: 96 planned test/security cases,
matching the experiment runner's case manifest. Its outputs remain incomplete
until every planned case has a recorded attempt.

## Corpus integrity and provenance

The persistent local Qdrant store contains **50,085 independent source records**
and **52,243 chunks**: 50,000 distinct HotpotQA source passages and 85 separately
labeled authored incident documents. Chunk count is not used as document count.
The full prepared corpus contains 108 evaluation questions, split into 92 test,
12 tuning and four security cases. Questions and support labels are not indexed.

The [preparation manifest](../data/manifests/hotpot-50k.json) pins the upstream
revision, seed, source-file hashes and licensing. The
[full reconciliation](../reports/performance/50k-concurrent/corpus-reconciliation.json)
checked every source ID, normalized stored-text checksum and source URI: 50,085
records checked, zero missing records, checksum mismatches, URI mismatches or
duplicate source IDs. Corpus revision:
`9e48a0b3-7f60-483b-86d9-5e7149562bb6`.

The same prepared corpus was imported into Qdrant Cloud: 50,085 created records,
zero failures and 52,243 chunks in 702.35 seconds. The
[cloud reconciliation](../reports/cloud-corpus-reconciliation.json) checked all
50,085 stored source IDs, normalized text checksums and URIs with zero mismatches.
Later disposable upload/replace/delete checks changed the corpus generation but
left the original source count unchanged. The v4 checkpoint binds its own exact
remote corpus revision; it must not be resumed after source mutations.

[Model provenance](../reports/model-provenance.json) records immutable model
revisions and actual downloaded-file hashes. Model downloads use those revisions
instead of an unversioned upstream branch. The semantic models are MiniLM-L6-v2
and BGE-small-en-v1.5; the reranker is MS MARCO MiniLM-L-6-v2.

## Full-corpus held-out evaluation

The [complete 92-case report](../reports/evaluation/50k-minilm-hybrid-extractive/report.md)
and [per-case predictions](../reports/evaluation/50k-minilm-hybrid-extractive/results.json)
use real MiniLM embeddings, structure chunks, hybrid retrieval, custom fusion and
cross-encoder reranking against all 50,085 documents. Generation provider is
`extractive`, with no live model synthesis or model verification calls.

| Measurement | Result | Applicable cases |
| --- | ---: | ---: |
| Recall@5 | 88.54% | 80 |
| Recall@10 | 89.58% | 80 |
| All required sources in top 10 | 75.00% | 80 |
| Mean reciprocal rank | 0.9838 | 80 |
| Gold-source citation precision | 45.35% | 80 |
| Gold-source citation recall | 80.42% | 80 |
| Exact stored-source quotation validity | 100.00% | 92 |
| Answer token F1, lexical diagnostic | 0.0944 | 80 |
| Required-fact recall, lexical diagnostic | 62.92% | 80 |
| Expected outcome/status accuracy | 85.87% | 92 |
| Conflict status accuracy | 100.00% | 12 |
| Unanswerable abstention accuracy | **0.00%** | 12 |
| Runtime errors | 0 | 92 |
| End-to-end p50 / p95 latency | 1,610 / 2,205 ms | 92 |

Recall averages required-source recovery per applicable question. All-support
recall requires every labeled supporting source. Source quotation validity checks
that emitted citations resolve exactly; it does not prove that the cited passage
entails a claim. Empty citation sets do not establish answer quality. See the
[metric definitions and denominators](EVALUATION_METHODOLOGY.md).

### Failure analysis

- Multi-hop retrieval is the clearest retrieval weakness: recall@10 is 77.0% and
  all-support recall is 44.1% across 34 multi-hop questions. A highly ranked first
  source does not compensate for a missing second source. The report retains
  concrete failed question IDs and retrieved passages for inspection.
- The 20 HotpotQA test cases have 90.0% recall@10 and 80.0% all-support recall on
  the full corpus. Authored incident cases have 89.4% and 73.3%, respectively.
  Read these source groups separately; synthetic cases alone do not establish
  general performance.
- Preview answers return excerpts instead of concise reference answers. Low
  token F1 and zero exact matches are expected consequences, but remain reported.
  Required-fact string matches can also occur in irrelevant surrounding text.
  The full-corpus browser example also retrieved similarly worded Nova and Morrow
  incidents alongside Atlas. Exact source quotes can still be irrelevant to the
  requested entity; generation and verification must explicitly test this.
- Preview mode returned material for all 12 unanswerable questions instead of
  withholding an answer. This is a measured failure. A live LLM run must test
  whether synthesis plus verification actually improves abstention.
- Numeric conflict handling matched all 12 authored conflict labels. This narrow
  result does not establish semantic conflict detection in arbitrary documents.

## Controlled configuration comparisons

The [five-configuration comparison](../reports/experiments/comparison.md) uses the
same 1,000 selected records and 96 test/security questions for every configuration.
Every required gold source is retained, then deterministic distractors fill the
selection. Tuning cases are excluded. This smaller corpus makes retrieval easier
and is not interchangeable with the 92-case full-corpus run.

| Configuration | Recall@10 | All-support@10 | Citation gold precision | p95 ms |
| --- | ---: | ---: | ---: | ---: |
| MiniLM, structure, hybrid, reranker | 93.21% | 81.48% | 52.57% | 2,182 |
| MiniLM, fixed, hybrid, reranker | 93.21% | 81.48% | 52.57% | 1,752 |
| MiniLM, structure, dense, reranker | 93.21% | 81.48% | 50.60% | 1,460 |
| MiniLM, structure, hybrid, no reranker | 96.91% | 92.59% | 33.93% | 159 |
| BGE-small, structure, hybrid, reranker | 93.21% | 81.48% | 51.98% | 2,452 |

All five final configurations completed with zero runtime errors. Their answer
provider is extractive. No answer-quality improvement from Gemini is inferred.
Short source passages produced no measured retrieval difference between the two
chunkers. BGE did not improve these aggregate retrieval scores. Removing the
reranker recovered more gold sources and reduced latency, but lowered citation
precision and preview status accuracy (56.52%, versus baseline 85.87%). This is a
tradeoff, not evidence that reranking always improves retrieval.

Indexes and model/embedding caches were reused where compatible. These latency
figures are not controlled cold-start measurements. The initial run suffered
11 large-batch reranker memory errors and an alternative-model download failure.
Its untouched [initial artifacts](../reports/experiments-initial/) remain available.
After reducing reranker batches to four and caching the pinned alternative model,
all configurations were rerun. No question was removed to hide a failure.

## Full-corpus performance

The [performance report](../reports/performance/50k-concurrent/benchmark.md) records
20 real investigations at concurrency two against the reconciled full corpus:
zero errors, p50 2,483 ms, p95 2,731 ms and throughput 0.782 requests/second.
Answer and retrieval-result caches were disabled; immutable embedding caching
remained enabled. Peak sampled process RSS was 2,276.6 MiB, sampled every 25 ms.
The sample can miss briefer allocation peaks.

This was Windows/Python 3.12 with local embedded Qdrant and extractive answers.
It includes embedded database memory and excludes LLM network latency. It does
not establish Render free-tier fit or remote Qdrant performance. Measure the
actual hosted configuration before claiming the deployment meets its limits.

## Remaining submission checks

1. Complete the real model evaluation across every required category. Native
   tools, structured synthesis and verification already work with actual Gemini
   responses. Preserve quota errors and failed cases; a partial checkpoint does
   not pass the evidence audit.
2. Repeat required chunking and retrieval comparisons with the same evaluated
   question manifest. The experiment runner uses test plus security; standalone
   evaluation defaults to test only. Compare matching manifests, not these two
   different case selections.
3. Inspect semantic entailment and missing evidence in the resulting answers.
   The [optional judge/review workflow](ANSWER_REVIEW.md) can assist, but valid
   quotations and lexical scores alone do not establish correctness.
4. Publish the final completed reports and rerun the evidence audit against the
   actual public service. Publication, all three public answer checks, remote
   corpus reconciliation and hosted restart persistence are verified below.

The automated suite currently passes 193 tests; Ruff, formatting, mypy and
JavaScript syntax checks also pass. Provider tests use mocked responses and do
not substitute for step one. Docker runtime verification remains uncompleted on
this host because the installed Docker Desktop engine failed to start; a Docker
build and nonroot runtime smoke have since passed on
[GitHub Actions](https://github.com/nikoo-dev/ai-investigation-engine/actions/runs/40780475600).
The runtime check imports the CPU ONNX provider, checks writable cache permissions,
and exercises upload/query and persistence across app lifespans. It uses synthetic
hash embeddings and extractive answers. Actual hosted inference and a separate
process-memory observation are recorded below.
The [captured CI result](../reports/ci/github-actions-db764a3.json) identifies its
actual source commit and individual check outcomes.

The [read-only browser check](../reports/ui/browser-check.json) against the full
corpus verified rendered findings, validated answer fragments followed by a final
object, a quote present in its stored passage, and desktop/mobile layouts without
horizontal page overflow or JavaScript page errors. It did not modify the corpus.
Screenshots are retained in `reports/ui/`. This verifies transport and UI behavior,
not the semantic correctness of the extractive preview.

The [checkpoint smoke verification](../reports/evaluation-checkpoint-verification.json)
used two actual CLI processes against the full local corpus: the first recorded
one of three planned questions, and the second resumed to all three. The original
completed prediction remained unchanged and both sessions used the same corpus
revision and software fingerprint. This checks cross-process recovery with real
retrieval and extractive answers; it makes no live Gemini claim.

## Public deployment observations

The [public application](https://ai-investigation-engine-h233.onrender.com)
returned a real Gemini conflict answer with three model calls, no retries and
both opposing audit quotations resolved to stored passages. The
[HTTP smoke artifact](../reports/deployment/public-smoke.json) records the actual
answer and 24.83-second cold query time. The
[lifecycle artifact](../reports/deployment/public-lifecycle.json) records an
unauthorized write rejected with 401, then authenticated TXT creation,
replacement to revision two, deletion and 404 on the deleted source.

After the candidate manually deployed commit `5ed377d`,
[restart observations](../reports/deployment/restart-evidence.json) recorded a
new process boot ID with the same source ID, revision and content checksum.
The original transition remains in `restart-5ed377d.json`; `restart-evidence.json`
now captures the later explicit model-change restart to commit `01328c6`.
Health and remote readiness both returned 200 after restart. The
[memory observation](../reports/deployment/hosted-memory.json) reports about
443 MiB of process RSS after model inference. This is one process observation,
not peak RSS, total container memory, or a guarantee of staying below a host limit.

The [public read-only browser check](../reports/deployment/ui/browser-readonly-check.json)
verified the real 50,085-document status, desktop/mobile layouts and mobile
document library without page errors or horizontal overflow. It makes no model
availability claim. The initial Gemini 3.5 answer-browser attempt stopped at the
unanswerable question when that model reached its daily quota. After explicitly
configuring Gemini 3.1, the separate
[three-question public browser run](../reports/deployment/ui/browser-check.json)
completed with `answered`, `conflicting_evidence` and `insufficient_evidence`,
zero request failures and zero JavaScript page errors. The causal answer names
CHG-001, the 250-millisecond timeout, payments-gateway, rollback and replay evidence.
The conflict answer quotes both audit exports; the unanswerable question invents
no financial-loss amount. Desktop/mobile screenshots show the actual outcomes.

[Cached copies captured immediately afterward](../reports/deployment/public-acceptance-gemini-3.1.json)
retain the complete answers and verify all five emitted source quotes against
their public stored passage and revision. These capture requests hit the answer
cache; the separate browser artifact records the original fresh generation calls.
The [hosted memory sampling](../reports/deployment/hosted-memory-sampled.json)
observed 180 successful one-second samples with a highest process RSS of 451.8
MiB during browser acceptance, on one unchanged boot. This can miss shorter
allocation peaks and excludes external Qdrant and container overhead.

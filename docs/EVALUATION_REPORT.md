# Measured evaluation and remaining evidence

Reviewed on 2026-10-29. The measurements below were recorded on 2026-10-27;
their original timestamps and individual predictions remain in the linked files.
These are real local ONNX retrieval and extractive-preview runs. **No live Gemini
evaluation or public deployment has been verified.** The preview is useful for
retrieval inspection, but its answer scores do not satisfy the LLM requirement.

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

1. Configure Gemini locally, verify native tool calls and structured synthesis,
   then record a real held-out evaluation of at least 40 questions across every
   required category. Preserve quota errors and failed cases.
2. Repeat required chunking and retrieval comparisons with the same evaluated
   question manifest. The experiment runner uses test plus security; standalone
   evaluation defaults to test only. Compare matching manifests, not these two
   different case selections.
3. Inspect semantic entailment and missing evidence in the resulting answers.
   The [optional judge/review workflow](ANSWER_REVIEW.md) can assist, but valid
   quotations and lexical scores alone do not establish correctness.
4. Publish the GitHub repository and public app, verify its actual memory and
   provider quotas, and capture hosted restart-persistence evidence using the
   [deployment guide](DEPLOYMENT.md) and [submission checklist](SUBMISSION_CHECKLIST.md).

The automated suite currently passes 191 tests; Ruff, formatting, mypy and
JavaScript syntax checks also pass. Provider tests use mocked responses and do
not substitute for step one. Docker runtime verification remains uncompleted on
this host because the installed Docker Desktop engine failed to start; a Docker
build check is included in CI for verification after publication.

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

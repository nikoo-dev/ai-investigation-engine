# Evaluation methodology

The harness records every prediction, source citation, reasoning trace, model/provider, embedding configuration, corpus revision and elapsed time. Reports are generated from these records; they are not hand-edited to improve scores.

## Corpora and held-out labels

`investigate prepare-dataset` downloads parquet data from the official `hotpotqa/hotpot_qa` repository at commit `1908d6afbbead072334abe2965f91bd2709910ab`. It never runs a dataset repository's Python loading script. Downloaded file hashes, subset hashes, record count, revision, source links, license and fixed seed are saved in `manifest.json`.

A record is a unique, independently attributable source passage, not a QA row or a chunk. Identity uses a SHA-256 hash of NFKC-normalized, whitespace-folded, casefolded complete passage text. The default primary corpus has 50,000 distinct HotpotQA passages, plus the separately identified authored incident fixture. Duplicate text does not inflate the corpus count.

The sampling procedure selects validation questions by SHA-256 of `seed:question-id`, alternating bridge and comparison questions. It adds all their context passages, including the supporting passages, before filling the corpus from a seeded order of training row groups and rows. This is a retrieval corpus: adding the evidence for a held-out question is intentional; the question, answer and supporting-fact labels are kept in the evaluation manifest and never indexed. Corpus metadata includes provenance and source sentences, not ground-truth answers.

The controlled incident fixture has 85 source documents and 88 questions. The 72 test questions comprise 12 direct, 12 comparison, 24 multi-hop, 12 unanswerable and 12 contradictory cases. Twelve tuning questions use two additional incidents whose supporting source documents are disjoint from the test incidents. Four prompt-injection probes form a separate security split. Each multi-hop case requires more than one source document. The optional HotpotQA selection adds 20 held-out questions. These controlled and encyclopedia results must be reported separately because their difficulty and failure modes differ.

The released `test` cases are held out from automated tuning. If changing thresholds or prompts based on an observed test failure, disclose that adaptation and evaluate new held-out cases before claiming an unbiased improvement. The harness records the case-manifest hash so configuration comparisons cannot silently use different questions.

## Metrics and denominators

| Metric | Meaning |
| --- | --- |
| Recall@5 / Recall@10 | Fraction of gold source documents found in the first K unique retrieved documents. |
| MRR | Reciprocal rank of the first relevant source, averaged over answerable cases with gold labels. |
| All-support@10 | Whether every required source is present in the first 10 unique documents; useful for multi-hop cases. |
| Evidence precision@10 | Fraction of returned unique top-10 documents that appear in the gold labels. |
| Answer token F1 / exact match | Casefolded, punctuation/article-normalized lexical agreement with reference answers. These are diagnostics, not full semantic correctness. |
| Required-fact recall | Fraction of authored required facts present as whole-word aliases. It detects omission but cannot prove that the answer asserts a fact correctly. |
| Citation gold precision / recall | Whether cited documents are relevant gold sources and whether all gold sources are cited. This is document-level relevance, not sentence-level entailment. |
| Citation source validity | Whether the cited passage exists and its document ID, revision and exact quoted text match stored evidence. |
| Claim citation coverage / ID validity | Whether answer claims contain citation IDs and whether those IDs resolve to returned citations. A valid ID alone does not prove entailment. |
| Abstention accuracy | Fraction of intentionally unanswerable cases returning `insufficient_evidence`. |
| Contradiction accuracy | Fraction of conflict cases returning `conflicting_evidence` with a nonempty conflict explanation. |
| Prompt-injection output safety | Narrow regex/exact-answer probes. Pair with integration tests that verify no mutations and no credential disclosure. |
| Error rate / p50 / p95 | Failure fraction and measured per-request end-to-end wall time. |

Each metric reports its applicable case count. Unanswerable questions have no retrieval gold labels and are excluded from retrieval metrics rather than given a misleading perfect score. Runtime/provider failures remain in applicable metric denominators. There is no answer-quality credit for returning an exception. Errors are recorded by exception type, not potentially secret-bearing request/response text.

The automated metrics do not establish claim-level entailment or semantic correctness. An optional human review should inspect at least five answers per category, every citation used by those claims, and every detected conflict, stating the reviewer and sampled case IDs. Do not describe token F1 as an LLM-judge or semantic correctness score.

## Checkpointed free-tier runs

After configuring and testing Gemini, start a separate output directory for its
real evaluation. The example below selects the same 92 held-out test questions on
every invocation:

```powershell
uv run investigate evaluate data/corpus/hotpot/cases.jsonl --name gemini-full --output reports/gemini-full --max-new-cases 5 --request-interval-seconds 15 --stop-on-error
uv run investigate evaluate data/corpus/hotpot/cases.jsonl --name gemini-full --output reports/gemini-full --max-new-cases 5 --request-interval-seconds 15 --stop-on-error --resume
```

Choose the interval and batch size from the quota actually available to the
project. Fifteen seconds is illustrative, not a guarantee. Pacing spaces model
HTTP attempt start times, including retries, across clients belonging to the same
engine. It does not coordinate other processes or API users, predict token usage,
or reset daily quotas. The CLI option avoids slowing the public application just
to pace an offline evaluation. A batch counts investigated questions, not provider
HTTP calls; one question can require several calls.

`checkpoint.json` is replaced atomically after each completed attempt. Ctrl+C
also writes a partial `results.json` and Markdown summary. A hard process kill
may leave the summary behind the checkpoint; resume reads the checkpoint and
rebuilds the summary. An interrupted in-flight provider request is not a completed
case and may consume quota again when resumed. No exactly-once billing guarantee
is made.

`--resume` skips every retained attempt, including failed attempts. `--stop-on-error`
records the failing case before stopping; after quota recovery, resuming proceeds
to the next case. Failures stay in the final denominators. To evaluate a repaired
system, use a new output directory and retain the original failed run. The audit
requires at least 40 completed live test cases across the required categories;
additional honestly recorded failures do not by themselves disqualify that evidence.

Resume validates the entire ordered case manifest, behavior configuration,
embedding fingerprint, Python source fingerprint, and exact corpus revision/count.
It rejects mismatches rather than mixing experiments. Do not change code or mutate
the corpus between sessions of the same run. A corpus change observed during a
run invalidates it. Pacing and batch size may change between sessions; the report
labels the latest session policy. A digest detects accidental checkpoint edits;
it does not authenticate the origin of model predictions.

Use one writer per output directory. Existing results without a checkpoint,
including the retained historical preview reports, require a new output directory.
Partial runs exit with code 2, show recorded/planned case counts, and cannot be
used for final comparison or submission evidence. `--split test-security` includes
the separate security probes alongside test questions, matching the experiment
runner; default standalone evaluation remains test-only.

## Required controlled comparisons

The five-configuration runner changes one factor at a time. Compare fixed-window and structure-aware chunking with hybrid retrieval, then dense-only and custom hybrid retrieval with structure chunks. Both comparisons keep the source corpus, embedding model, LLM and question manifest constant. Further configurations compare reranking on/off and a second embedding model. This is not a full factorial study of every combination. Separate indexes are required when vector dimensions, models or chunking change; reusing an incompatible collection invalidates the experiment.

Save each run's `results.json` and `report.md`, then use the comparison command. Compare retrieval coverage, answer diagnostics, citation accuracy, abstention/conflict decisions, latency and cost together. Document failures and mechanisms before selecting a default. A configuration is not a winner because one aggregate metric improved while multi-hop coverage or safety regressed.

## Scale and reproducibility checks

Verify at least 50,000 active source documents through the store's own count after ingestion, not from a downloaded file's row count. Compare the manifest IDs to active document IDs to detect duplicate suppression or failed indexing. Restart the app/store and recheck counts and a sample of source citations.

The benchmark command executes uncached requests with configurable repeats and concurrency. It records measured p50/p95, throughput, errors, machine information, exact corpus revision/count, provider and sampled process RSS. RSS sampling can miss transient peaks. A local Qdrant client may use exact scans, so report Qdrant-server latency separately before extrapolating. Free-tier hosted latency and cold-start behavior must be measured on the public URL; local measurements are not evidence of hosted performance.

For each submission report, distinguish actual results from pending external checks. An extractive answer run or hash-embedding test fixture is useful for deterministic regression testing, but does not satisfy the assignment's real LLM and semantic embedding requirements.

## Source attribution

HotpotQA is distributed under [CC BY-SA 4.0](https://hotpotqa.github.io/); retain attribution and the source title/URL when redistributing passages. The official [dataset card](https://huggingface.co/datasets/hotpotqa/hotpot_qa) supplies the schema and repository revision. Authored incident fixtures are explicitly synthetic and released as CC0-1.0.

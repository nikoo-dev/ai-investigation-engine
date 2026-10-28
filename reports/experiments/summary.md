# Controlled retrieval and chunking experiments

Generated: 2026-10-27T14:19:42.146795+00:00. Status: complete.

Each configuration uses **1000 identical source records** and **96 identical cases**. Split counts: `{'test': 92, 'security': 4}`.

Selected corpus SHA-256: `a959d2f4ae18e821c7ab9bb606c8865029b1cc7a9090c5127a23631cb5502bd8`. Evaluation SHA-256: `93fc8001faf5ec5039c6a7fce7eada4dd1a6922c528bf608e9b767e749079e66`.

The first row is the baseline. Every other row changes one factor only. Scores include failure cases in their applicable denominators.

Configuration | Contrast | Recall@10 | All-support@10 | MRR | Token F1 | Citation validity | Error rate | p95 ms
--- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---:
minilm-structure-hybrid-rerank | baseline | 0.9321 | 0.8148 | 1.0000 | 0.0951 | 1.0000 | 0.0000 | 2182.2042
minilm-fixed-hybrid-rerank | chunking | 0.9321 | 0.8148 | 1.0000 | 0.0951 | 1.0000 | 0.0000 | 1752.4417
minilm-structure-dense-rerank | hybrid-search | 0.9321 | 0.8148 | 1.0000 | 0.0920 | 1.0000 | 0.0000 | 1459.5323
minilm-structure-hybrid-no-rerank | reranking | 0.9691 | 0.9259 | 1.0000 | 0.0647 | 1.0000 | 0.0000 | 159.2940
bge-small-structure-hybrid-rerank | embedding-model | 0.9321 | 0.8148 | 1.0000 | 0.0948 | 1.0000 | 0.0000 | 2451.5947

## Actual model execution

- `minilm-structure-hybrid-rerank`: embedding `fastembed:sentence-transformers/all-MiniLM-L6-v2:384:v1`; providers `{'extractive': 96}`; models `{'source-excerpts': 96}`; usage totals `{}`.
- `minilm-fixed-hybrid-rerank`: embedding `fastembed:sentence-transformers/all-MiniLM-L6-v2:384:v1`; providers `{'extractive': 96}`; models `{'source-excerpts': 96}`; usage totals `{}`.
- `minilm-structure-dense-rerank`: embedding `fastembed:sentence-transformers/all-MiniLM-L6-v2:384:v1`; providers `{'extractive': 96}`; models `{'source-excerpts': 96}`; usage totals `{}`.
- `minilm-structure-hybrid-no-rerank`: embedding `fastembed:sentence-transformers/all-MiniLM-L6-v2:384:v1`; providers `{'extractive': 96}`; models `{'source-excerpts': 96}`; usage totals `{}`.
- `bge-small-structure-hybrid-rerank`: embedding `fastembed:BAAI/bge-small-en-v1.5:384:v1`; providers `{'extractive': 96}`; models `{'source-excerpts': 96}`; usage totals `{}`.

## Interpretation

- This controlled subset ablation does not replace the separate >=50,000-record ingestion and load test.
- Gold source inclusion is guaranteed, not gold ranking. Only source passages are indexed; questions and reference answers remain outside searchable text.
- Test and security cases are reported separately in each report; tuning cases are excluded.
- Repeated configurations share embedding caches and compatible indexes; latency includes per-engine lazy reranker/model initialization and is not a clean cold-start benchmark.
- Extractive-provider answers measure an evidence-only fallback, not LLM reasoning. Actual providers/models and usage totals are reported per configuration.
- Token F1 and source-label citation metrics are proxies; inspect per-case predictions and claim entailment before claiming semantic correctness.

Read the per-configuration reports for source/split breakdowns and failure analysis. The complete selected IDs are in `selection.json`; unedited per-case answers, citations and traces are retained in each `results.json`.

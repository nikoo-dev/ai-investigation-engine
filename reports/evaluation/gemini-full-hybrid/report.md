# Evaluation: gemini-full-hybrid

Generated: 2026-10-28T22:16:18.870982+00:00

Run status: partial; 1 / 92 planned cases recorded.

Cases: 1. Corpus: `{'documents': 50085, 'chunks': 52243, 'corpus_revision': '9e48a0b3-7f60-483b-86d9-5e7149562bb6', 'backend': 'qdrant_local'}`.

Evaluation SHA-256: `f62286775e4f46c62e2165c9c8b71ace2e1b53f83c30781efd053e5dd67c5381`.

## Configuration

```json
{
  "embedding_backend": "fastembed",
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "embedding_dimension": 384,
  "chunk_strategy": "structure",
  "chunk_tokens": 256,
  "chunk_overlap": 40,
  "bm25_avg_length": 150.0,
  "retrieval_limit": 30,
  "evidence_limit": 12,
  "retrieval_mode": "hybrid",
  "reranker_enabled": true,
  "reranker_model": "Xenova/ms-marco-MiniLM-L-6-v2",
  "llm_provider": "gemini",
  "llm_model": "gemini-3.5-flash-lite",
  "min_dense_score": 0.25,
  "max_tool_calls": 6,
  "max_subquestions": 4,
  "max_context_chars": 22000
}
```

## Quantitative results

Metric | Mean | Applicable cases
--- | ---: | ---:
recall_at_5 | 0.0000 | 1
recall_at_10 | 0.0000 | 1
mrr | 0.0000 | 1
all_support_at_10 | 0.0000 | 1
evidence_precision_at_10 | 0.0000 | 1
answer_token_f1 | 0.0000 | 1
answer_exact_match | 0.0000 | 1
answer_fact_recall | 0.0000 | 1
status_accuracy | 0.0000 | 1
citation_gold_precision | 0.0000 | 1
citation_gold_recall | 0.0000 | 1
citation_source_validity | 0.0000 | 1
error_rate | 1.0000 | 1
elapsed_ms | 5923.7482 | 1
latency_p50_ms | 5923.7482 | -
latency_p95_ms | 5923.7482 | -

## Results by question category

Category | Cases | Recall@10 | All-support@10 | Status accuracy | Answer token F1
--- | ---: | ---: | ---: | ---: | ---:
multi_hop | 1 | 0.000 | 0.000 | 0.000 | 0.000

## Corpus-source separation

- `hotpotqa-validation`: 1 cases; Recall@10 0.0000; all-support@10 0.0000; token F1 0.0000.

## Split isolation

- `test`: 1 cases; status accuracy 0.0000.
Do not report tuning-set scores as held-out results. The aggregate above includes only the cases passed to this run; use the test split for the submission's final quality claim.

## Failure analysis

- `hotpot-5ae63b2255429908198fa526` (multi_hop): What is the date played of this college football game at Sun Life Stadium in Miami Gardens, Florida, where Clemson defeated the No. 4 Oklahoma Sooners, 37-17?
  - Runtime/provider failure; inspect the saved case error and retry under the same configuration.
  - Metrics: `{'recall_at_5': 0.0, 'recall_at_10': 0.0, 'mrr': 0.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.0, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 1.0, 'elapsed_ms': 5923.74819998804}`

## Interpretation and limitations

- Token F1/exact match and required-fact recall are lexical diagnostics, not proof of semantic correctness.
- Citation gold precision checks relevance against source-document labels; source validity checks exact quote, document and revision. Neither proves claim-level entailment.
- Prompt-injection output checks catch specific probes only; mutation side effects and secret leakage require the separate integration tests.
- The authored incident set is a controlled robustness fixture; HotpotQA held-out questions measure a different, open-domain task. Report them separately.
- An extractive/hash test run does not satisfy the real LLM/semantic-search requirement. Provider and embedding configuration are recorded above.
- Partial runs are not final evidence. Resume requires identical cases, behavior settings, software and corpus; previous failures are retained and never silently retried.
- Session pacing and batch size can change on resume. Cumulative active duration includes pacing and checkpoint writes, not time between sessions. Only the latest session policy is shown.

Full predictions, labels, citations and traces are in `results.json`. No predictions were edited after generation.

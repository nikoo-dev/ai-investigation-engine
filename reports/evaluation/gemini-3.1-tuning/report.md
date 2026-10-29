# Evaluation: gemini-3.1-tuning

Generated: 2026-10-29T00:23:42.545538+00:00

Run status: complete; 12 / 12 planned cases recorded.

Cases: 12. Corpus: `{'documents': 50085, 'chunks': 52243, 'corpus_revision': '0e23207b-25d9-46b1-a1d2-5b6fbe72a648', 'backend': 'qdrant_remote'}`.

Evaluation SHA-256: `d4a77d8c8bd1ec11bc9c26103808b6c94b63b2e2199f2e099fec60827af1302e`.

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
  "llm_model": "gemini-3.1-flash-lite",
  "min_dense_score": 0.25,
  "max_tool_calls": 6,
  "max_subquestions": 4,
  "max_context_chars": 22000
}
```

## Quantitative results

Metric | Mean | Applicable cases
--- | ---: | ---:
recall_at_5 | 0.9667 | 10
recall_at_10 | 1.0000 | 10
mrr | 0.8833 | 10
all_support_at_10 | 1.0000 | 10
evidence_precision_at_10 | 0.2300 | 10
answer_token_f1 | 0.3751 | 10
answer_exact_match | 0.0000 | 10
answer_fact_recall | 0.8000 | 10
status_accuracy | 1.0000 | 12
citation_gold_precision | 0.9250 | 10
citation_gold_recall | 1.0000 | 10
citation_source_validity | 1.0000 | 10
claim_citation_id_validity | 1.0000 | 8
claim_citation_coverage | 1.0000 | 8
error_rate | 0.0000 | 12
elapsed_ms | 19087.4251 | 12
contradiction_accuracy | 1.0000 | 2
abstention_accuracy | 1.0000 | 2
latency_p50_ms | 18509.6350 | -
latency_p95_ms | 28690.2611 | -

## Results by question category

Category | Cases | Recall@10 | All-support@10 | Status accuracy | Answer token F1
--- | ---: | ---: | ---: | ---: | ---:
comparison | 2 | 1.000 | 1.000 | 1.000 | 0.457
contradictory | 2 | 1.000 | 1.000 | 1.000 | 0.222
direct | 2 | 1.000 | 1.000 | 1.000 | 0.321
multi_hop | 4 | 1.000 | 1.000 | 1.000 | 0.438
unanswerable | 2 | n/a | n/a | 1.000 | n/a

## Corpus-source separation

- `authored-incidents`: 12 cases; Recall@10 1.0000; all-support@10 1.0000; token F1 0.3751.

## Split isolation

- `tuning`: 12 cases; status accuracy 1.0000.
Do not report tuning-set scores as held-out results. The aggregate above includes only the cases passed to this run; use the test split for the submission's final quality claim.

## Failure analysis

- `conflict-13` (contradictory): How many payment requests failed during Morrow incident INC-013, according to the two audit exports?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.25, 'answer_token_f1': 0.2222222222222222, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': 1.0, 'citation_gold_precision': 1.0, 'citation_gold_recall': 1.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 12684.03259999468}`
- `conflict-14` (contradictory): How many payment requests failed during Nova incident INC-014, according to the two audit exports?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.25, 'answer_token_f1': 0.2222222222222222, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': 1.0, 'citation_gold_precision': 1.0, 'citation_gold_recall': 1.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 13916.597199990065}`

## Interpretation and limitations

- Token F1/exact match and required-fact recall are lexical diagnostics, not proof of semantic correctness.
- Citation gold precision checks relevance against source-document labels; source validity checks exact quote, document and revision. Neither proves claim-level entailment.
- Prompt-injection output checks catch specific probes only; mutation side effects and secret leakage require the separate integration tests.
- The authored incident set is a controlled robustness fixture; HotpotQA held-out questions measure a different, open-domain task. Report them separately.
- An extractive/hash test run does not satisfy the real LLM/semantic-search requirement. Provider and embedding configuration are recorded above.
- Partial runs are not final evidence. Resume requires identical cases, behavior settings, software and corpus; previous failures are retained and never silently retried.
- Session pacing and batch size can change on resume. Cumulative active duration includes pacing and checkpoint writes, not time between sessions. Only the latest session policy is shown.

Full predictions, labels, citations and traces are in `results.json`. No predictions were edited after generation.

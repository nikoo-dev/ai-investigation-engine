# Evaluation: gemini-cloud-hybrid-v4

Generated: 2026-10-28T23:56:58.318369+00:00

Run status: partial; 25 / 92 planned cases recorded.

Cases: 25. Corpus: `{'documents': 50085, 'chunks': 52243, 'corpus_revision': '0e23207b-25d9-46b1-a1d2-5b6fbe72a648', 'backend': 'qdrant_remote'}`.

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
recall_at_5 | 0.7000 | 25
recall_at_10 | 0.7733 | 25
mrr | 0.9000 | 25
all_support_at_10 | 0.5600 | 25
evidence_precision_at_10 | 0.2000 | 25
answer_token_f1 | 0.1764 | 25
answer_exact_match | 0.0000 | 25
answer_fact_recall | 0.6400 | 25
status_accuracy | 0.6400 | 25
citation_gold_precision | 0.6800 | 25
citation_gold_recall | 0.5533 | 25
citation_source_validity | 0.6800 | 25
claim_citation_id_validity | 1.0000 | 16
claim_citation_coverage | 1.0000 | 16
error_rate | 0.0400 | 25
elapsed_ms | 16008.4974 | 25
latency_p50_ms | 14837.9278 | -
latency_p95_ms | 21115.7191 | -

## Results by question category

Category | Cases | Recall@10 | All-support@10 | Status accuracy | Answer token F1
--- | ---: | ---: | ---: | ---: | ---:
comparison | 10 | 0.800 | 0.600 | 0.500 | 0.163
multi_hop | 15 | 0.756 | 0.533 | 0.733 | 0.186

## Corpus-source separation

- `authored-incidents`: 5 cases; Recall@10 0.6667; all-support@10 0.4000; token F1 0.2819.
- `hotpotqa-validation`: 20 cases; Recall@10 0.8000; all-support@10 0.6000; token F1 0.1501.

## Split isolation

- `test`: 25 cases; status accuracy 0.6400.
Do not report tuning-set scores as held-out results. The aggregate above includes only the cases passed to this run; use the test split for the submission's final quality claim.

## Failure analysis

- `hotpot-5a7fb1765542992e7d278d20` (multi_hop): Why does the City of Boston get their christmas tree from Ainslee Glen Nova Scotia?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.25, 'answer_token_f1': 0.16666666666666669, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 1.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 14458.987600010005}`
- `hotpot-5ae234005542994d89d5b392` (comparison): Who has the highest scope in profession in  Rob Thomas or  James Dean Bradfield
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.5, 'recall_at_10': 0.5, 'mrr': 0.5, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.125, 'answer_token_f1': 0.13636363636363635, 'answer_exact_match': 0.0, 'answer_fact_recall': 1.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 9616.407900000922}`
- `hotpot-5a80ad19554299485f5986a8` (multi_hop): In addition to his role in The Fattest Man in Britain, Bobby Ball is best known for his half of the doublt act Cannon and Ball with which other comedian?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.5, 'recall_at_10': 0.5, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.125, 'answer_token_f1': 0.19999999999999998, 'answer_exact_match': 0.0, 'answer_fact_recall': 1.0, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 0.5, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 14708.712899999227}`
- `hotpot-5ab56f3e5542992aa134a317` (comparison): Which genus of flowering plant is found in an environment further south, Crocosmia or Cimicifuga?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.5, 'recall_at_10': 0.5, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.125, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 9704.39109999279}`
- `hotpot-5a75d9b4554299109176e5a7` (multi_hop): What type of crab can be grown in a fishery and is known for its sweet and tender flesh?
  - The expected answer/abstention/conflict decision did not match. Inspect evidence coverage and conflicting claims; tune thresholds only on a separate tuning split.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 0.5, 'citation_source_validity': 1.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 15457.638499996392}`
- `hotpot-5ae6050f55429929b0807a5e` (multi_hop): This singer of A Rather Blustery Day also voiced what hedgehog?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.5, 'recall_at_10': 0.5, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.125, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 9275.380000006407}`
- `hotpot-5a8c5b635542996e8ac88a75` (comparison): Which breed, Chinese Chongqing Dog or Kanni, is used for hunting?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.5, 'recall_at_10': 0.5, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.125, 'answer_token_f1': 0.05555555555555556, 'answer_exact_match': 0.0, 'answer_fact_recall': 1.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 9911.515400002827}`
- `hotpot-5ae2138c5542997283cd23b7` (comparison): Are Villa Paletti and Betrayal at House on the Hill both board games?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 1.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 20932.037799997488}`
- `hotpot-5a86eee85542994775f60787` (multi_hop):  During what years did the railroad that had a station stop in Ringling, Montana operate?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.5, 'recall_at_10': 0.5, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.125, 'answer_token_f1': 0.05263157894736842, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 9551.525300004869}`
- `hotpot-5a8e8af55542990e94052b3f` (comparison): Which university is a private research university, University of California, Berkeley or Brown University?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.5, 'recall_at_10': 0.5, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.125, 'answer_token_f1': 0.5, 'answer_exact_match': 0.0, 'answer_fact_recall': 1.0, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 0.5, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 14837.92779999203}`
- `hotpot-5a7363ec5542991f29ee2dd7` (multi_hop): The USS Tortuga was named after the Dry Tortugas, a group of desert coral islets 60 miles west of which city with the motto "One Human Family"?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.5, 'recall_at_10': 0.5, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.125, 'answer_token_f1': 0.33333333333333337, 'answer_exact_match': 0.0, 'answer_fact_recall': 1.0, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 0.5, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 14497.461699997075}`
- `hotpot-5ab73de755429928e1fe383b` (comparison): Which item spanned farther distances regarding sales, Interact Home Computer or Sord M5?
  - The expected answer/abstention/conflict decision did not match. Inspect evidence coverage and conflicting claims; tune thresholds only on a separate tuning split.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 21115.7191000093}`
- `hotpot-5ac41f1d5542991943173924` (comparison): Is Ohio State University or California State University, Dominguez Hills further west?
  - The expected answer/abstention/conflict decision did not match. Inspect evidence coverage and conflicting claims; tune thresholds only on a separate tuning split.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 0.5, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.18181818181818182, 'answer_exact_match': 0.0, 'answer_fact_recall': 1.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 16890.964700010954}`
- `cause-01` (multi_hop): Which system change caused the Atlas payment delay on March 3, which service was affected, and what confirmed the cause?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.375, 'answer_token_f1': 0.3714285714285714, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 1.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 18936.86170000001}`
- `cause-02` (multi_hop): Which system change caused the Birch payment delay on March 4, which service was affected, and what confirmed the cause?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.375, 'answer_token_f1': 0.3333333333333333, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 1.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 19518.62030000484}`
- `cause-03` (multi_hop): Which system change caused the Cobalt payment delay on March 5, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.25, 'answer_token_f1': 0.3278688524590164, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 19435.45129999984}`
- `cause-04` (multi_hop): Which system change caused the Delta payment delay on March 6, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.25, 'answer_token_f1': 0.37681159420289856, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 19586.81290000095}`
- `cause-05` (multi_hop): Which system change caused the Ember payment delay on March 7, which service was affected, and what confirmed the cause?
  - Runtime/provider failure; inspect the saved case error and retry under the same configuration.
  - Metrics: `{'recall_at_5': 0.0, 'recall_at_10': 0.0, 'mrr': 0.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.0, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 1.0, 'elapsed_ms': 28579.391200008104}`

## Interpretation and limitations

- Token F1/exact match and required-fact recall are lexical diagnostics, not proof of semantic correctness.
- Citation gold precision checks relevance against source-document labels; source validity checks exact quote, document and revision. Neither proves claim-level entailment.
- Prompt-injection output checks catch specific probes only; mutation side effects and secret leakage require the separate integration tests.
- The authored incident set is a controlled robustness fixture; HotpotQA held-out questions measure a different, open-domain task. Report them separately.
- An extractive/hash test run does not satisfy the real LLM/semantic-search requirement. Provider and embedding configuration are recorded above.
- Partial runs are not final evidence. Resume requires identical cases, behavior settings, software and corpus; previous failures are retained and never silently retried.
- Session pacing and batch size can change on resume. Cumulative active duration includes pacing and checkpoint writes, not time between sessions. Only the latest session policy is shown.

Full predictions, labels, citations and traces are in `results.json`. No predictions were edited after generation.

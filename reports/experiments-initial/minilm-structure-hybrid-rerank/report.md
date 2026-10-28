# Evaluation: minilm-structure-hybrid-rerank

Generated: 2026-10-27T14:14:23.257683+00:00

Cases: 96. Corpus: `{'documents': 1000, 'chunks': 1033, 'corpus_revision': 'ba2fff3f-7f45-40de-8f3b-fce5d4ae79b2', 'backend': 'qdrant_local'}`.

Evaluation SHA-256: `93fc8001faf5ec5039c6a7fce7eada4dd1a6922c528bf608e9b767e749079e66`.

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
  "llm_provider": "extractive",
  "llm_model": "gemini-3.5-flash-lite",
  "min_dense_score": 0.25
}
```

## Quantitative results

Metric | Mean | Applicable cases
--- | ---: | ---:
recall_at_5 | 0.7819 | 81
recall_at_10 | 0.7963 | 81
mrr | 0.8642 | 81
all_support_at_10 | 0.6790 | 81
evidence_precision_at_10 | 0.1531 | 81
answer_token_f1 | 0.0911 | 80
answer_exact_match | 0.0000 | 80
answer_fact_recall | 0.5292 | 80
status_accuracy | 0.7391 | 92
citation_gold_precision | 0.4152 | 81
citation_gold_recall | 0.7078 | 81
citation_source_validity | 0.8854 | 96
claim_citation_id_validity | 1.0000 | 56
claim_citation_coverage | 1.0000 | 56
error_rate | 0.1146 | 96
elapsed_ms | 767.2808 | 96
contradiction_accuracy | 1.0000 | 12
injection_output_safety | 1.0000 | 4
abstention_accuracy | 0.0000 | 12
latency_p50_ms | 471.2527 | -
latency_p95_ms | 2415.9378 | -

## Results by question category

Category | Cases | Recall@10 | All-support@10 | Status accuracy | Answer token F1
--- | ---: | ---: | ---: | ---: | ---:
comparison | 22 | 0.773 | 0.773 | 0.727 | 0.076
contradictory | 12 | 1.000 | 1.000 | 1.000 | 0.031
direct | 12 | 1.000 | 1.000 | 1.000 | 0.049
multi_hop | 34 | 0.662 | 0.382 | 0.824 | 0.137
prompt_injection | 4 | 1.000 | 1.000 | n/a | n/a
unanswerable | 12 | n/a | n/a | 0.000 | n/a

## Corpus-source separation

- `authored-incidents`: 76 cases; Recall@10 0.9098; all-support@10 0.7541; token F1 0.1086.
- `hotpotqa-validation`: 20 cases; Recall@10 0.4500; all-support@10 0.4500; token F1 0.0383.

## Split isolation

- `security`: 4 cases; status accuracy 0.0000.
- `test`: 92 cases; status accuracy 0.7391.
Do not report tuning-set scores as held-out results. The aggregate above includes only the cases passed to this run; use the test split for the submission's final quality claim.

## Failure analysis

- `hotpot-5a80ad19554299485f5986a8` (multi_hop): In addition to his role in The Fattest Man in Britain, Bobby Ball is best known for his half of the doublt act Cannon and Ball with which other comedian?
  - Runtime/provider failure; inspect the saved case error and retry under the same configuration.
  - Metrics: `{'recall_at_5': 0.0, 'recall_at_10': 0.0, 'mrr': 0.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.0, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 1.0, 'elapsed_ms': 0}`
- `hotpot-5ab56f3e5542992aa134a317` (comparison): Which genus of flowering plant is found in an environment further south, Crocosmia or Cimicifuga?
  - Runtime/provider failure; inspect the saved case error and retry under the same configuration.
  - Metrics: `{'recall_at_5': 0.0, 'recall_at_10': 0.0, 'mrr': 0.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.0, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 1.0, 'elapsed_ms': 0}`
- `hotpot-5a75d9b4554299109176e5a7` (multi_hop): What type of crab can be grown in a fishery and is known for its sweet and tender flesh?
  - Runtime/provider failure; inspect the saved case error and retry under the same configuration.
  - Metrics: `{'recall_at_5': 0.0, 'recall_at_10': 0.0, 'mrr': 0.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.0, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 1.0, 'elapsed_ms': 0}`
- `hotpot-5add647a5542995b365fab26` (comparison): What is the main difference between Aloinopsis and Washingtonia?
  - Runtime/provider failure; inspect the saved case error and retry under the same configuration.
  - Metrics: `{'recall_at_5': 0.0, 'recall_at_10': 0.0, 'mrr': 0.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.0, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 1.0, 'elapsed_ms': 0}`
- `hotpot-5ae6050f55429929b0807a5e` (multi_hop): This singer of A Rather Blustery Day also voiced what hedgehog?
  - Runtime/provider failure; inspect the saved case error and retry under the same configuration.
  - Metrics: `{'recall_at_5': 0.0, 'recall_at_10': 0.0, 'mrr': 0.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.0, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 1.0, 'elapsed_ms': 0}`
- `hotpot-5a8c5b635542996e8ac88a75` (comparison): Which breed, Chinese Chongqing Dog or Kanni, is used for hunting?
  - Runtime/provider failure; inspect the saved case error and retry under the same configuration.
  - Metrics: `{'recall_at_5': 0.0, 'recall_at_10': 0.0, 'mrr': 0.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.0, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 1.0, 'elapsed_ms': 0}`
- `hotpot-5abc089b5542993f40c73c57` (multi_hop): MacBook offers what brand-type of displays that are higher-resolution than other portable computers?
  - Runtime/provider failure; inspect the saved case error and retry under the same configuration.
  - Metrics: `{'recall_at_5': 0.0, 'recall_at_10': 0.0, 'mrr': 0.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.0, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 1.0, 'elapsed_ms': 0}`
- `hotpot-5ae2138c5542997283cd23b7` (comparison): Are Villa Paletti and Betrayal at House on the Hill both board games?
  - Runtime/provider failure; inspect the saved case error and retry under the same configuration.
  - Metrics: `{'recall_at_5': 0.0, 'recall_at_10': 0.0, 'mrr': 0.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.0, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 1.0, 'elapsed_ms': 0}`
- `hotpot-5a86eee85542994775f60787` (multi_hop):  During what years did the railroad that had a station stop in Ringling, Montana operate?
  - Runtime/provider failure; inspect the saved case error and retry under the same configuration.
  - Metrics: `{'recall_at_5': 0.0, 'recall_at_10': 0.0, 'mrr': 0.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.0, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 1.0, 'elapsed_ms': 0}`
- `hotpot-5a8e8af55542990e94052b3f` (comparison): Which university is a private research university, University of California, Berkeley or Brown University?
  - Runtime/provider failure; inspect the saved case error and retry under the same configuration.
  - Metrics: `{'recall_at_5': 0.0, 'recall_at_10': 0.0, 'mrr': 0.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.0, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 1.0, 'elapsed_ms': 0}`
- `hotpot-5a7b3ec95542995eb53be8d3` (multi_hop): Edward C. Hugger and Alexander Acosta served at appointees for what job?
  - Runtime/provider failure; inspect the saved case error and retry under the same configuration.
  - Metrics: `{'recall_at_5': 0.0, 'recall_at_10': 0.0, 'mrr': 0.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.0, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 0.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 1.0, 'elapsed_ms': 0}`
- `hotpot-5a8a5c0d554299515336137b` (multi_hop): What professional dancers twice turned on a lights festival taking place on the Fylde Coast in Lancashire?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 1.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 2357.226799998898}`
- `cause-01` (multi_hop): Which system change caused the Atlas payment delay on March 3, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.2588235294117647, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.6, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 424.6295999910217}`
- `cause-02` (multi_hop): Which system change caused the Birch payment delay on March 4, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.2588235294117647, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.6, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 424.0107000223361}`
- `cause-03` (multi_hop): Which system change caused the Cobalt payment delay on March 5, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.2588235294117647, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.6, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 397.7868000220042}`
- `cause-04` (multi_hop): Which system change caused the Delta payment delay on March 6, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.3333333333333333, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.09876543209876544, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.25, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.4, 'citation_gold_recall': 0.3333333333333333, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 719.5248999923933}`
- `cause-05` (multi_hop): Which system change caused the Ember payment delay on March 7, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.3333333333333333, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.09876543209876544, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.25, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.4, 'citation_gold_recall': 0.3333333333333333, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 1084.3937000026926}`
- `cause-06` (multi_hop): Which system change caused the Fjord payment delay on March 8, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.2588235294117647, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.6, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 944.1590000060387}`
- `cause-07` (multi_hop): Which system change caused the Garnet payment delay on March 9, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.2588235294117647, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.6, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 967.3295999818947}`
- `cause-08` (multi_hop): Which system change caused the Helix payment delay on March 10, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.24719101123595508, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 1986.663599993335}`

## Interpretation and limitations

- Token F1/exact match and required-fact recall are lexical diagnostics, not proof of semantic correctness.
- Citation gold precision checks relevance against source-document labels; source validity checks exact quote, document and revision. Neither proves claim-level entailment.
- Prompt-injection output checks catch specific probes only; mutation side effects and secret leakage require the separate integration tests.
- The authored incident set is a controlled robustness fixture; HotpotQA held-out questions measure a different, open-domain task. Report them separately.
- An extractive/hash test run does not satisfy the real LLM/semantic-search requirement. Provider and embedding configuration are recorded above.

Full predictions, labels, citations and traces are in `results.json`. No predictions were edited after generation.

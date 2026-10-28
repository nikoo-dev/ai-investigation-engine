# Evaluation: minilm-structure-dense-rerank

Generated: 2026-10-27T14:17:09.334260+00:00

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
  "retrieval_mode": "dense",
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
recall_at_5 | 0.9177 | 81
recall_at_10 | 0.9321 | 81
mrr | 1.0000 | 81
all_support_at_10 | 0.8148 | 81
evidence_precision_at_10 | 0.1802 | 81
answer_token_f1 | 0.0920 | 80
answer_exact_match | 0.0000 | 80
answer_fact_recall | 0.6094 | 80
status_accuracy | 0.8152 | 92
citation_gold_precision | 0.5060 | 81
citation_gold_recall | 0.7922 | 81
citation_source_validity | 1.0000 | 96
claim_citation_id_validity | 1.0000 | 63
claim_citation_coverage | 1.0000 | 63
error_rate | 0.0000 | 96
elapsed_ms | 621.6498 | 96
contradiction_accuracy | 1.0000 | 12
injection_output_safety | 1.0000 | 4
abstention_accuracy | 0.0000 | 12
latency_p50_ms | 555.9852 | -
latency_p95_ms | 1474.0319 | -

## Results by question category

Category | Cases | Recall@10 | All-support@10 | Status accuracy | Answer token F1
--- | ---: | ---: | ---: | ---: | ---:
comparison | 22 | 1.000 | 1.000 | 0.818 | 0.074
contradictory | 12 | 1.000 | 1.000 | 1.000 | 0.031
direct | 12 | 1.000 | 1.000 | 1.000 | 0.049
multi_hop | 34 | 0.838 | 0.559 | 0.971 | 0.140
prompt_injection | 4 | 1.000 | 1.000 | n/a | n/a
unanswerable | 12 | n/a | n/a | 0.000 | n/a

## Corpus-source separation

- `authored-incidents`: 76 cases; Recall@10 0.9098; all-support@10 0.7541; token F1 0.1045.
- `hotpotqa-validation`: 20 cases; Recall@10 1.0000; all-support@10 1.0000; token F1 0.0545.

## Split isolation

- `security`: 4 cases; status accuracy 0.0000.
- `test`: 92 cases; status accuracy 0.8152.
Do not report tuning-set scores as held-out results. The aggregate above includes only the cases passed to this run; use the test split for the submission's final quality claim.

## Failure analysis

- `hotpot-5ab56f3e5542992aa134a317` (comparison): Which genus of flowering plant is found in an environment further south, Crocosmia or Cimicifuga?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.4, 'citation_gold_recall': 1.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 687.610399996629}`
- `hotpot-5a75d9b4554299109176e5a7` (multi_hop): What type of crab can be grown in a fishery and is known for its sweet and tender flesh?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 0.5, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 846.8058000144083}`
- `hotpot-5ae2138c5542997283cd23b7` (comparison): Are Villa Paletti and Betrayal at House on the Hill both board games?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.8, 'citation_gold_recall': 1.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 520.2751999895554}`
- `hotpot-5a8a5c0d554299515336137b` (multi_hop): What professional dancers twice turned on a lights festival taking place on the Fylde Coast in Lancashire?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 1.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 1231.1095999903046}`
- `cause-01` (multi_hop): Which system change caused the Atlas payment delay on March 3, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.2588235294117647, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.6, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 934.5935999881476}`
- `cause-02` (multi_hop): Which system change caused the Birch payment delay on March 4, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.2588235294117647, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.6, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 470.84649998578243}`
- `cause-03` (multi_hop): Which system change caused the Cobalt payment delay on March 5, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.2588235294117647, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.6, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 423.2538999931421}`
- `cause-04` (multi_hop): Which system change caused the Delta payment delay on March 6, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.3333333333333333, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.09876543209876544, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.25, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.4, 'citation_gold_recall': 0.3333333333333333, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 455.8177999861073}`
- `cause-05` (multi_hop): Which system change caused the Ember payment delay on March 7, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.3333333333333333, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.09876543209876544, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.25, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.4, 'citation_gold_recall': 0.3333333333333333, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 471.32650000276044}`
- `cause-06` (multi_hop): Which system change caused the Fjord payment delay on March 8, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.0, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 421.26760000246577}`
- `cause-07` (multi_hop): Which system change caused the Garnet payment delay on March 9, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.2588235294117647, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.6, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 420.98409999744035}`
- `cause-08` (multi_hop): Which system change caused the Helix payment delay on March 10, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.24719101123595508, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 352.01959998812526}`
- `cause-09` (multi_hop): Which system change caused the Indigo payment delay on March 11, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.11764705882352941, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.25, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.8, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 439.0514999977313}`
- `cause-10` (multi_hop): Which system change caused the Jasper payment delay on March 12, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.24719101123595508, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 788.5755999886896}`
- `cause-11` (multi_hop): Which system change caused the Kestrel payment delay on March 13, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.24719101123595508, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 750.9092999971472}`
- `cause-12` (multi_hop): Which system change caused the Lumen payment delay on March 14, which service was affected, and what confirmed the cause?
  - At least one required source was outside the top ten unique documents. Investigate query decomposition, lexical entity matching, reranker truncation and candidate coverage before changing generation.
  - Metrics: `{'recall_at_5': 0.6666666666666666, 'recall_at_10': 0.6666666666666666, 'mrr': 1.0, 'all_support_at_10': 0.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.24719101123595508, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.75, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 1.0, 'citation_gold_recall': 0.6666666666666666, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 919.7166999801993}`
- `comparison-01` (comparison): Which incident delayed payments longer, Atlas or Birch, and for how many minutes each?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.10256410256410257, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.6666666666666666, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.4, 'citation_gold_recall': 1.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 770.6124999967869}`
- `comparison-02` (comparison): Which incident delayed payments longer, Birch or Cobalt, and for how many minutes each?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.10256410256410257, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.6666666666666666, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.4, 'citation_gold_recall': 1.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 687.8620999923442}`
- `comparison-03` (comparison): Which incident delayed payments longer, Cobalt or Delta, and for how many minutes each?
  - The generated answer missed at least one labeled fact or used an unrecognized alias. Manually inspect the claim/source links before attributing this to retrieval or generation.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.10256410256410257, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.6666666666666666, 'status_accuracy': 1.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.4, 'citation_gold_recall': 1.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': 1.0, 'claim_citation_coverage': 1.0, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 755.2006000187248}`
- `comparison-04` (comparison): Which incident delayed payments longer, Delta or Ember, and for how many minutes each?
  - The expected answer/abstention/conflict decision did not match. Inspect evidence coverage and conflicting claims; tune thresholds only on a separate tuning split.
  - Metrics: `{'recall_at_5': 1.0, 'recall_at_10': 1.0, 'mrr': 1.0, 'all_support_at_10': 1.0, 'evidence_precision_at_10': 0.2, 'answer_token_f1': 0.0625, 'answer_exact_match': 0.0, 'answer_fact_recall': 0.0, 'status_accuracy': 0.0, 'abstention_accuracy': None, 'contradiction_accuracy': None, 'citation_gold_precision': 0.0, 'citation_gold_recall': 0.0, 'citation_source_validity': 1.0, 'claim_citation_id_validity': None, 'claim_citation_coverage': None, 'injection_output_safety': None, 'error_rate': 0.0, 'elapsed_ms': 646.2821000022814}`

## Interpretation and limitations

- Token F1/exact match and required-fact recall are lexical diagnostics, not proof of semantic correctness.
- Citation gold precision checks relevance against source-document labels; source validity checks exact quote, document and revision. Neither proves claim-level entailment.
- Prompt-injection output checks catch specific probes only; mutation side effects and secret leakage require the separate integration tests.
- The authored incident set is a controlled robustness fixture; HotpotQA held-out questions measure a different, open-domain task. Report them separately.
- An extractive/hash test run does not satisfy the real LLM/semantic-search requirement. Provider and embedding configuration are recorded above.

Full predictions, labels, citations and traces are in `results.json`. No predictions were edited after generation.

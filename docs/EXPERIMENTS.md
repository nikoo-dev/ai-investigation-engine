# Reproducible configuration experiments

The experiment runner measures five configurations on the same independently attributed source records and the same held-out questions:

| Configuration | Change from the baseline |
| --- | --- |
| MiniLM, structure chunks, hybrid search, reranking | Baseline |
| MiniLM, fixed chunks, hybrid search, reranking | Chunking strategy |
| MiniLM, structure chunks, dense search, reranking | Dense retrieval versus hybrid retrieval |
| MiniLM, structure chunks, hybrid search, no reranking | Cross-encoder reranking |
| BGE-small-en-v1.5, structure chunks, hybrid search, reranking | Semantic embedding model |

Both semantic models have 384 dimensions, but their vectors remain in different indexes. Their actual tokenizer budgets can differ; the title prefix and passage are both included in budget checks. Therefore the embedding comparison measures the model together with its usable passage capacity, not embedding weights under an artificially identical token window.

## Run

Prepare the full corpus and download the standard models first using the README commands. Invoke the runner from Python, or use the CLI's `experiments` command when available:

```python
from pathlib import Path

from investigation.config import Settings
from investigation.experiments import run_experiments

run_experiments(
    Settings(),
    corpus_path=Path("data/corpus/hotpot/corpus.jsonl"),
    cases_path=Path("data/corpus/hotpot/cases.jsonl"),
    output_dir=Path("reports/experiments"),
    minimum_records=1000,
    include_alternative_model=True,
    seed=42,
)
```

`EMBEDDING_BACKEND=fastembed` is required. Tests use injected fixtures, but normal runs cannot report hash embeddings as semantic results. The BGE model is downloaded on its first run; network access is required unless it is already cached.

The runner includes all `test` and `security` questions and excludes `tuning` questions. It first retains every required gold source, then selects distractors by ascending SHA-256 of `seed:source-id` until it reaches the requested minimum. If the gold set itself exceeds that minimum, every gold source remains included. Source ordering in the input JSONL does not change selection. Missing gold sources, conflicting duplicate IDs, too few independent records, failed ingestion, or a changed evaluation manifest fail the run explicitly.

Only source passages and their attribution metadata enter the vector index. Evaluation questions, reference answers, and support labels remain in the evaluation manifest.

## Persistence and resources

The main application's `data/qdrant` directory is never opened by the experiment runner. Each model/chunk/corpus combination gets a stable separate index under `.cache/experiments/indexes/`. Retrieval and reranking ablations reuse a compatible index. Runs execute sequentially and close each local Qdrant client before opening the next, so the experiment can run while a different process owns the main application's local database.

Embedding model files, embedding vectors, and reranker model files reuse the configured `DATA_DIR/cache` directory. These caches do not share document state. If parameters or selected source records change, the index identity changes rather than mixing incompatible vectors. A replay may count source records as duplicates because they are already indexed; it still checks the final independent document count against the exact selected corpus.

Do not commit vector stores, model binaries, or caches. Retain the generated reports and their manifests as submission evidence. The source corpus's license and attribution obligations still apply to any source passages quoted in saved predictions.

## Reports and interpretation

`selection.json` records the selected and gold IDs, seed, source-file hash, normalized selection hash, source counts, and exact selection algorithm. `summary.json` records all configurations, their index identities, independent source counts, ingestion timing, actual embedding fingerprints, actual answer providers/models, and total reported usage. `summary.md` and `comparison.md` show the measured tradeoffs. Each configuration retains `results.json` with every prediction, quote, citation, trace, and error, plus its own Markdown failure analysis.

The test/security and authored-incident/HotpotQA breakdowns must be read separately. Token F1, required-fact recall, and gold-source citation metrics are useful diagnostics, not proof of claim entailment or general reasoning quality. Failed cases remain in the appropriate denominators.

An `extractive` run measures retrieval and the evidence-only fallback; it does not satisfy the assignment's real LLM requirement. When Gemini or Ollama is configured, the runner records the actual provider and token usage for every prediction. Provider errors are retained rather than replaced by invented successful results. A completed experiment with errors is labeled accordingly per configuration.

This 1,000-or-more-record controlled experiment complements the full 50,000-record ingestion, evaluation, and load test; it does not establish full-corpus performance. Cached models and reused compatible indexes also mean its latency is not a rigorous cold-start benchmark. Compare answer quality with the dedicated performance report before choosing a deployment default. Final test results are for reporting; use the separate tuning split for threshold changes.

## Run real-provider comparisons in batches

Use a fresh output folder to preserve the historical preview experiments:

The current selected provider/model is `gemini` / `gemini-3.1-flash-lite`.
The matching full-cloud evaluation uses `--split test-security` (96 cases).
Keep the 1,000-record controlled comparison separate from that full-scale run:
corpus size changes retrieval difficulty, so compare the five controlled
configurations with each other rather than attributing differences between
the 1,000- and 50,085-record corpora to the chunker or retrieval mode.

```powershell
uv run investigate experiments data/corpus/hotpot/corpus.jsonl data/corpus/hotpot/cases.jsonl --output reports/gemini-3.1-experiments --records 1000 --max-new-cases 5 --request-interval-seconds 15 --stop-on-error
uv run investigate experiments data/corpus/hotpot/corpus.jsonl data/corpus/hotpot/cases.jsonl --output reports/gemini-3.1-experiments --records 1000 --max-new-cases 5 --request-interval-seconds 15 --stop-on-error --resume
```

The batch cap applies per configuration. The runner stops at the first partial
configuration, and subsequent invocations resume it before advancing. Completed
configurations reuse their checkpoints without new model calls. Compatible
indexes are reopened and idempotent ingestion is checked. Pacing starts anew when
an engine is created for another configuration; it is not an account-wide limiter.
Choose actual pacing/batch limits from the project's available quota.

Keep software, selected corpus, configuration plan and provider/model unchanged
throughout a resumed experiment. Partial summaries show recorded/planned counts;
a final comparison is written only after all configurations finish. Error rows
are retained. See the [checkpoint rules](EVALUATION_METHODOLOGY.md#checkpointed-free-tier-runs).

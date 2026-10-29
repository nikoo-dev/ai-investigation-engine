# Five-minute investigation demo

The main demonstration must use a real configured LLM and real semantic
embeddings. Extractive preview is useful for checking local plumbing, but does
not satisfy the LLM or multi-step synthesis requirement. Hash embeddings are
only offline test fixtures and must not be presented as semantic retrieval.

## Prepare before the demonstration

Use the README and deployment guide for account/secret setup. The public app,
remote corpus and restart persistence are verified in `reports/deployment/`.
Gemini 3.1 Flash-Lite passed all 12 reserved tuning cases; the full evaluation
and matching live configuration comparisons still need complete reports.
Check current provider quota before the timed demonstration. Never display
API keys or the management token while screen sharing.

1. Install the locked environment:

   ```text
   uv sync --frozen --extra dev --extra data
   ```

2. Configure `.env` from `.env.example` without overwriting an existing secret
   file. For the final demo use `EMBEDDING_BACKEND=fastembed`,
   `LLM_PROVIDER=gemini`, an accessible `LLM_MODEL`, and `GEMINI_API_KEY`. Use the
   production remote Qdrant configuration for the public URL. Do not commit keys.
3. Before starting a local web process, prepare/index the corpus and confirm
   readiness. Embedded local Qdrant permits one process at a time; stop the web
   server before CLI indexing or inspecting that same data directory.

   ```text
   uv run investigate download-models
   uv run investigate prepare-dataset --records 50000 --seed 42
   uv run investigate ingest data/corpus/hotpot/corpus.jsonl
   uv run investigate status
   ```

   The prepared corpus already includes the authored incident documents used by
   the examples. Check the active stored document count is at least 50,000 and
   investigate any ingestion failures. A downloaded file's row count is not proof
   of a successfully indexed corpus.
4. For a small development rehearsal only, `uv run investigate seed --ingest`
   indexes the 85 authored source documents. Label that rehearsal as a small
   fixture, not the final dataset/scale demonstration.
5. Run the final evaluation before the demo and keep the actual reports open.
   Use the same provider/model/corpus shown in the demonstration. Account quotas
   can limit the number of LLM calls; verify them and leave time between requests
   as needed rather than repeatedly resubmitting after `429`.
6. Start locally with `uv run investigate serve`, or open the verified public
   HTTPS URL. Check `/health` and `/ready`. If the free service is asleep, allow
   the documented cold-start interval before the timed demo. Confirm the UI
   provider status does not say **Evidence preview mode**.

## 0:00–0:40 — Establish what is running

Open the investigation workspace. Show the connected corpus count, explain that
each record is an independently attributable source passage, and show the actual
model/provider. Open the document library briefly to demonstrate that source
documents, revisions, status and passage counts are visible.

Say: “The same Python pipeline serves the browser and evaluation CLI. Semantic
and keyword candidates are combined by our custom fusion algorithm, then
reranked. Claims must point to exact stored evidence.”

Do not describe the synthetic incident reports as real company incidents. They
are controlled, labeled fixtures within the public-data corpus.

## 0:40–2:00 — Show a multi-document investigation

Ask the first suggestion:

> Which system change caused the Atlas payment delay on March 3, which service
> was affected, and what confirmed the cause?

Show the progress stages and open the investigation trace after the answer.
Check the answer against the actual documents; the intended fixture chain is:

- CHG-001 reduced the database connection timeout to 250 milliseconds.
- The affected service was `payments-gateway`.
- Rollback and controlled replay in the later verification note confirmed the
  causal relationship; the initial incident report alone recorded correlation.

Open a claim citation and show its exact stored passage, document title, revision
and location. Then inspect the second source needed for the reasoning chain.
Explain why a plausible answer with only the first report would be incomplete.

If the answer omits a required link or cites the wrong project, demonstrate the
actual failure and use the trace/report to explain it. Do not substitute a
prewritten successful answer for the runtime output.

## 2:00–2:45 — Show a source conflict

Ask:

> How many payment requests failed during Atlas incident INC-001, according to
> the two audit exports?

The two fixture audit exports disagree: one reports 101 requests and the other
301 for the same incident/date. The expected behavior is `conflicting_evidence`,
an explanation of the disagreement, and citations to both exports. Open both
passages. The system should not silently average the values, choose one without
evidence, or confuse a different incident's count with this one.

## 2:45–3:20 — Show honest abstention

Ask:

> What was the exact financial revenue loss in euros caused by Atlas incident
> INC-001?

The controlled corpus does not establish the exact euro loss. The expected
behavior is `insufficient_evidence`, explaining the missing fact. No invented
amount, including zero, is acceptable. Related service/duration evidence does
not establish a financial figure.

## 3:20–4:10 — Demonstrate document lifecycle

Use a small public TXT/DOCX/PDF created for the demo, not a sensitive file. In the
library, upload it and show the indexed result. Replace it with changed content
and show the revision advance. Delete only that demo document and show it is
removed. Production writes require the management token; enter it privately
before the demonstration through **Management access**.

Explain that the store first prepares a new revision's chunks, then publishes
its document marker. Removed or superseded evidence must not remain a valid
source. The hosted persistence check should already have been performed and
recorded by restarting/redeploying the app and rechecking its sources/counts.
Do not claim hosted persistence from a local-only test.

## 4:10–5:00 — Show measured quality and limitations

Open the actual generated evaluation comparison. Show the case count and
manifest hash, Recall@K/MRR/all-support retrieval, exact citation validity,
abstention/conflict outcomes and latency. Explain one concrete failure and why
it occurs. Show that fixed/structure and dense/hybrid comparisons used the same
source corpus and questions. A second real model experiment should be labeled
with its actual model/configuration, not inferred from an adapter's existence.

State the limits plainly: lexical answer F1 is not semantic correctness; manual
claim/citation review is required; the same LLM's verifier can share its errors;
free-tier cold starts and quotas affect latency; progress/final responses stream
but raw unchecked answer tokens are withheld. Finish on the actual GitHub and
public-demo links, README, evaluation report and AI disclosure.

## Rehearsal checklist

- Real provider and semantic model are active; the interface shows no preview warning.
- Active stored corpus count, source provenance and required scale are verified.
- All three question categories were actually exercised; failures are documented.
- Source quotations resolve to current stored passages and revisions.
- The management token is private; demo upload content is public and disposable.
- The public URL, restart persistence, reports and links have been tested.
- Candidate can explain and modify the relevant code without an AI assistant.

If credentials are unavailable, use extractive preview only as a development
walkthrough and say explicitly that the real LLM evaluation/public submission
gates are still open.

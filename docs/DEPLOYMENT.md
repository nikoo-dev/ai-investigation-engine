# Free deployment: exact setup and acceptance steps

The code is prepared for GitHub + Render + Qdrant Cloud + Gemini. Creating those
accounts and granting access is a user action. No live deployment is implied by
the presence of this guide. Use only the free plans below and do not enable paid
upgrades or model billing to complete the assignment.

## 1. Gemini access

1. Sign in to [Google AI Studio](https://aistudio.google.com/).
2. Create/select a project and create a Gemini API key. Keep billing disabled if
   you want the free-tier quota to be a hard spending boundary.
3. Copy `.env.example` to `.env` locally. Set `GEMINI_API_KEY`, `LLM_PROVIDER=gemini`,
   and `LLM_MODEL=gemini-3.1-flash-lite`.
4. Verify the model is available to your project. This workspace verified native
   tools, structured output and all 12 reserved tuning cases with 3.1 Flash-Lite.
   Both generation and tool-call access must work with the selected key. Free
   model availability and quotas are project-specific; check the current guide.
5. Run `uv run investigate ask "What changed in Atlas CHG-001?"` after seeding data.
   Confirm the answer reports `provider: gemini` and nonzero model-call usage.

Do not paste keys in chat, commit them, put them in a URL, or enter the Gemini key
in the browser's management-token field. Google's free API may use submitted
content to improve its products, so this demo should use public/synthetic data.
Read the [model guide](https://ai.google.dev/gemini-api/docs/models),
[free-tier pricing](https://ai.google.dev/gemini-api/docs/pricing), and
[project-specific rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

## 2. Qdrant Cloud

1. Sign up at [Qdrant Cloud](https://cloud.qdrant.io/).
2. Create one **Free** cluster. Do not select Standard or paid capacity. Current
   documentation lists 1 GB RAM, 0.5 vCPU, 4 GB disk, and no credit-card requirement.
3. Copy its HTTPS cluster endpoint and API key to `.env` as `QDRANT_URL` and
   `QDRANT_API_KEY`. Use the HTTPS port supported by your cluster, normally 6333.
4. Keep `COLLECTION_PREFIX=investigation` and the default embedding/chunk settings
   identical between import and deployment.
5. From your local machine run:

```powershell
uv run investigate prepare-dataset
uv run investigate ingest data/corpus/hotpot/corpus.jsonl --batch-size 128
uv run investigate status
```

6. Confirm at least 50,000 `documents` and a successful import job. Record the exact
   count and corpus revision. Start the local app against this same remote cluster
   and verify upload, query, source inspection, replacement, and deletion.
7. Create a manual snapshot before the final demonstration. Store backup artifacts
   privately; source text may contain uploaded material.

Qdrant's current free cluster may suspend after one inactive week and be deleted
after four inactive weeks. Keep a reproducible corpus manifest and export important
uploads separately; an inactive free database is not permanent archival storage.
See [the current cluster limits and lifecycle](https://qdrant.tech/documentation/cloud/create-cluster/).

## 3. GitHub repository

The [submission repository](https://github.com/nikoo-dev/ai-investigation-engine)
is already public for this workspace. The following publication steps also
document how to reproduce that setup for another repository.

1. Sign in to or create your [GitHub account](https://github.com/).
2. Authenticate GitHub CLI with `gh auth login` (the system browser flow keeps the
   token out of shell history). Existing invalid authentication must be renewed.
3. Review `.gitignore`, `git status`, and the AI usage report. Ensure `.env`, raw
   datasets, cached models, vector stores, and generated secrets are untracked.
4. Use meaningful commits. Create the submission repository from the project root:

```powershell
gh repo create ai-investigation-engine --public --source=. --remote=origin --push
```

5. Confirm GitHub Actions passes. Inspect the public repository in a signed-out
   window and check that code, fixture manifests, documentation, and measured
   reports are present. Dataset downloads are reproduced by command rather than
   storing hundreds of megabytes in Git.

## 4. Render free service

After the Qdrant cluster is populated, this
[preconfigured Render deployment link](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Fnikoo-dev%2Fai-investigation-engine)
opens the published repository's Blueprint setup. Review the Free plan and enter
the secret environment values in Render before deploying. The link itself does
not provision infrastructure or supply credentials.

The actual deployment for this workspace is
[ai-investigation-engine-h233.onrender.com](https://ai-investigation-engine-h233.onrender.com).
Readiness, real Gemini conflict synthesis, TXT lifecycle and restart persistence
are recorded in `reports/deployment/`. Pushing Git commits did not restart this
particular service during verification; use **Manual Deploy -> Deploy latest
commit** when necessary and confirm the checkout SHA in Render's logs. Do not
infer the running code from the GitHub branch alone.

1. Sign up at [Render](https://dashboard.render.com/) using the GitHub account.
2. Choose **New -> Blueprint**, select the repository, and use its `render.yaml`.
3. Verify the web service's plan is **Free**. The repository specifies Docker.
4. Enter `QDRANT_URL`, `QDRANT_API_KEY`, and `GEMINI_API_KEY` in Render's secret
   environment settings. `ADMIN_TOKEN` is generated by the blueprint. Copy that
   token privately for document-management access.
5. Verify `ENVIRONMENT=production`, `LLM_PROVIDER=gemini`, and the same
   `COLLECTION_PREFIX`, embedding model, dimension, and chunk settings used by the
   local import. Do not re-ingest the dataset during startup.
   The blueprint allows one investigation at a time and three guarded requests
   per minute. A query can make up to four model calls before bounded retries;
   these limits keep the public demonstration conservative about free API quotas.
6. Deploy and wait for `/health` to pass. Open the assigned `https://...onrender.com`
   URL. Confirm `/ready` can reach Qdrant and the UI shows the actual document count.
7. Enter **only** `ADMIN_TOKEN` in the UI's management-access dialog. It stays in
   browser session storage and is sent as a bearer header for writes.

Current Render free services sleep after 15 minutes idle and may need about a
minute to wake. They have no persistent local disk and a monthly free-instance
hour allowance. Render's free Postgres expires, so this architecture does not use
it. All documents/chunks/jobs are in Qdrant; model and query caches can be rebuilt.
Read [Render's current free-service limitations](https://render.com/docs/free).

Watch memory after an actual query with reranking. The free plan has a small memory
budget. Keep one worker and one simultaneous investigation. The cross-encoder uses
small inference batches; if measured memory still exceeds the available limit,
disable reranking for the hosted demo (`RERANKER_ENABLED=false`) while preserving
and reporting the locally measured reranker comparison. Hybrid retrieval and the
custom fusion component remain active. Do not claim reranking is enabled if it is
disabled. Core functionality must still be tested in the hosted configuration.

## 5. Public acceptance test and evidence

Run these in the deployed app and record the URL, commit SHA, date, and results:

1. In a signed-out browser, load the public HTTPS URL and ask the seeded causal
   question. Check `provider=gemini`, a multi-step trace, and sources from multiple
   documents. Confirm each claim and quoted span in its source drawer.
2. Ask a contradictory audit question and an unanswerable financial-loss question.
   Check conflict and abstention behavior without fabricated facts.
3. Confirm unauthorized document writes return 401. Add a text document with admin
   access, replace it, inspect the incremented revision, and delete it.
4. Add a unique persistence-test document; record its ID. Restart the Render service
   and verify the same document and source passages remain accessible. Delete the
   test document afterward.
5. After an idle sleep, load the URL again and verify recovery rather than treating
   the cold-start page as an application failure.
6. Run the test evaluation against the same remote collection with the same model
   configuration; save the real results and error rate. Free API quotas may require
   pacing across multiple sessions/days. Use the [checkpointed evaluation commands](EVALUATION_METHODOLOGY.md#checkpointed-free-tier-runs)
   to retain work across sessions, and the [batched comparison commands](EXPERIMENTS.md#run-real-provider-comparisons-in-batches)
   for required configuration comparisons. Preserve failures rather than deleting them.
7. Add the verified repository/live URLs and measured report links to the submission
   checklist. Do not submit a local-only URL as the live demo.

## Local Docker verification

```powershell
docker compose up --build -d
docker compose exec app investigate seed --ingest
docker compose exec app investigate status
```

Open <http://127.0.0.1:8000>. Qdrant uses the `qdrant_data` named volume and model
caches use `model_cache`. `docker compose down` preserves these volumes. Do not use
`down -v` unless you intentionally want to erase the local database and caches.
The embedded fallback is suitable for one process; production requires a remote
Qdrant URL and an admin token.

## Recovery

- Provider 429/503: the app retries within a bound, then reports unavailability.
  Check current project quotas; do not create uncontrolled retry loops.
  A daily quota error is not fixed by redeploying Render or creating another key
  for the same project. Retain the evaluation checkpoint and resume after quota
  recovery. A different supported free model requires an explicit `LLM_MODEL`
  configuration and a new evaluation directory; never merge different models
  into one checkpoint. During actual verification, Gemini 3.5 Flash-Lite reported
  the project's 500-request daily model quota. Gemini 3.1 Flash-Lite is being
  checked separately and passed all 12 tuning cases. The blueprint now explicitly
  selects it; an existing service must update `LLM_MODEL` and redeploy. No automatic
  fallback is implemented.
- Qdrant unavailable: inspect cluster suspension/status and `/ready`; do not
  initialize an empty replacement database and call the original data preserved.
- Incompatible collection signature: restore the matching configuration or choose
  a new prefix and reindex. Never mix model dimensions or chunk policies in place.
- Interrupted ingestion: replay the identical hashed corpus. The job records
  progress and completed source IDs/checksums are idempotent.
- Lost model cache: allow the pinned dependencies to download model assets again.
  It is not the durable source of truth.

# Submission evidence checklist

Copy `submission.example.json` to `submission.json` and replace every empty value
with a real URL or project-relative artifact path. Empty values are intentional:
the example does not fabricate a GitHub repository, public demo, provider run or
human review. Do not put credentials in this manifest.

The read-only `audit_submission(project_root, manifest_path, store=None,
check_urls=False)` function lives in
[`submission.py`](../src/investigation/submission.py). It does not initialize an
embedding model, open a database directory, publish anything, or modify reports.
The CLI integrates this audit separately. Without an injected open `Store`, it
reports the active database count as **unverified**. Without URL checks, it
reports publication, public readiness and restart persistence as **unverified**.

## Evidence to supply

| Manifest field | Required evidence |
| --- | --- |
| `repository_url` | Actual public `https://github.com/account/repository`. URL checks require the current local commit to resolve through GitHub's public commit endpoint. Private repositories require separate authorized verification and cannot pass this unauthenticated check. |
| `live_demo_url` | Public HTTPS application base URL. URL checks GET `/health` and `/ready` with a five-second timeout and redirects disabled. Local/private IPs and obvious placeholder URLs are rejected. |
| `dataset_manifest` | Generated preparation manifest, preferably the committed `data/manifests/hotpot-50k.json`; it records 50,000+ primary source records, exact corpus/case hashes, source revision, seed, license and source URL. If raw files exist beside it or at `data/corpus/hotpot`, their hashes are checked. Otherwise actual raw-file integrity is explicitly unverified. This gate records preparation evidence; it never replaces the injected Store's active count or manifest-ID reconciliation. |
| `evaluation_report` | Generated `results.json` from 40+ test questions covering direct, comparison, multi-hop, unanswerable and contradictory cases, using real semantic embeddings and Gemini/Ollama calls. The report retains all rows, including failures. Preview/hash/zero-call/cached outcomes do not qualify as live evaluation. |
| `comparison_reports` | Measured result JSON paths using the same evaluated case manifest. Include fixed/structure and dense/hybrid comparisons. Use separate compatible collection prefixes; never mix vectors or chunk settings. |
| `manual_review_report` | Optional named human review bound to the exact evaluation file hash. If supplied, the package validates at least five actual reviews per category using the schema below. This is recommended preparation, not an additional assignment requirement. AI-written text claiming a human review is not a review. |
| `deployment_evidence` | Captured before/after health and source responses from the same public URL, with different application boot IDs and an unchanged document ID/revision/checksum. The current live health and source responses must match the captured after state. |

The audit also checks the required documentation and the existence of actual
local Git history. It imposes no arbitrary minimum commit count. Publishing a
local commit does not prove that later uncommitted changes were published;
review `git status` and commit the final intended source before the final audit.

## Capture restart persistence

1. On the real public application, GET `/health` and a ready source through
   `/api/v1/documents/{id}`. Record their actual response objects, the application
   base URL, who captured them, and the observation time including timezone.
2. Restart/redeploy the application through the hosting provider. Do not delete
   or rebuild the vector database. Wait for `/ready` to confirm readiness.
3. Capture `/health` and the same document again, and record the second observation
   time. `boot_id` must differ and the second instance's `started_at` must be
   later than the first observation. The document ID, revision and checksum must
   remain unchanged.
4. Keep this evidence as JSON inside the project. Run URL verification while the
   second instance is still current. A later restart changes its boot ID and
   requires a fresh capture pair for the current-instance check.

Required shape (illustrative field names; replace with actual captured objects):

```json
{
  "base_url": "https://your-actual-public-app-host",
  "captured_by": "Name of the person or tool recording these observations",
  "observed_before_at": "ISO 8601 timestamp with timezone",
  "observed_after_at": "ISO 8601 timestamp with timezone",
  "health_before": {"status": "ok", "boot_id": "actual UUID", "started_at": "actual UTC timestamp"},
  "health_after": {"status": "ok", "boot_id": "different actual UUID", "started_at": "actual UTC timestamp"},
  "document_before": {"id": "actual source UUID", "revision": 1, "checksum": "actual SHA-256"},
  "document_after": {"id": "same source UUID", "revision": 1, "checksum": "same actual SHA-256"}
}
```

A bare `"restarted": true` or an operator statement does not pass. Distinct
captured application instances plus current matching HTTP state provide stronger
evidence. They are still recorded observations, not cryptographic proof that a
historical capture was authentic. Keep provider deployment/restart logs with
the evidence for review; do not manufacture before/after JSON.

## Record actual manual answer review

Review the generated answers and every cited source for at least five cases in
each required category. Use actual test IDs from the report. Inspect claim
entailment, completeness, conflict handling and missing evidence, not just valid
citation identifiers. Describe failures honestly; fix serious issues and rerun
before approving the final artifact. Hash the final `results.json` after the
run; modifying that file invalidates its linked review.

```json
{
  "reviewer_kind": "human",
  "reviewer": "Actual reviewer name",
  "reviewed_at": "Actual ISO 8601 timestamp with timezone",
  "evaluation_file_sha256": "SHA-256 of the actual results.json bytes",
  "approved": true,
  "cases": [
    {
      "case_id": "Actual test case ID",
      "citation_entailment_checked": true,
      "outcome": "supported",
      "notes": "Specific observation from checking this answer and its actual source passages."
    }
  ]
}
```

Allowed review outcomes are `supported`, `withheld_correctly`, and
`documented_failure`; the latter requires a candid finding and acceptable
documented limitation, not a fabricated success. Approval is the named human's
attestation. The audit validates its completeness and binding, but does not
independently observe that review.

## Read the audit result correctly

The result contains `status: pass|incomplete` and individual checks with details,
evidence and evidence levels. It reports every missing gate in one invocation.
A reported runtime/provider error remains an evaluation failure; failures are
not removed to reach 40 successful cases. Resolve missing evidence and rerun the
audit rather than hand-editing its output.

Each check records `required`. An absent optional human review is shown as
unverified with `required: false`; it does not block submission. If a review is
supplied, its contents are checked rather than assumed to be authentic.

Passing checks provide a consistent evidence package, not a promise of a perfect
assessment score. Current Store counts do not replace complete manifest-ID
reconciliation, and lexical metrics do not replace human semantic review.
Before submission also inspect the full [requirements matrix](REQUIREMENTS.md),
actual benchmark/model-comparison artifacts and [AI disclosure](AI_USAGE_REPORT.md).

The public demo and final Gemini evaluation remain pending until their actual
artifacts and external observations exist. Optional human review is not claimed.

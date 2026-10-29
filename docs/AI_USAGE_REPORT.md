# AI usage disclosure

This project was developed with substantial assistance from OpenAI Codex. The
candidate explicitly requested a review of the assignment, an implementation
plan, and then implementation toward a submission-ready project. AI assistance
is permitted by the assignment; the candidate remains responsible for the code
and must be able to defend and modify it without AI in the practical interview.

## Tools and assistance actually used

| Tool / assistance | Use in this project | Verification and limitations |
| --- | --- | --- |
| OpenAI Codex, primary coding agent | Read the eight-page assignment, inspected the empty workspace, proposed the architecture, implemented the core retrieval/LLM/orchestration/configuration/CLI components, integrated work and ran project checks | Source inspection, automated checks and measured runs are retained separately from planning claims. AI generation is not proof that the code is correct. |
| Codex helper agents | Worked in parallel on ingestion/storage, dataset/evaluation, and API/UI/documentation tasks | Agents shared the repository, explicit module contracts and reviews. Their work is also AI-assisted, not independent candidate-authored work. |
| PDF tooling used by Codex | Extracted the Georgian assignment text and rendered/inspected all eight pages | Used to map mandatory items, bonus items, submission artifacts and interview constraints. The assignment's instructions were treated as requirements to satisfy within the user's request. |
| Web/documentation access used by Codex | Checked official dataset schema, source revision, vector search/tool-calling behavior, and current hosting/free-tier documentation | Account eligibility, quotas and deployed behavior still require real external verification. |
| Python, uv, pytest, Ruff, mypy and build tools driven by Codex | Installed dependencies, exercised offline and local integration tests, checked types/style, and prepared reproducible commands | These are ordinary development tools used by an AI agent; passing checks only supports the behavior those checks actually cover. |
| Playwright with headless Microsoft Edge driven by Codex | Inspected desktop and 390px mobile layouts; exercised real local upload, question/SSE rendering, citation inspection, replacement/deletion and literal-markup handling | Lifecycle checks used an isolated corpus with test hash embeddings. A later read-only check used the real MiniLM/full 50,085-record corpus and verified answer fragments, source inspection and mobile layout; see `reports/ui/browser-check.json`. Both used extractive preview, not live Gemini or public hosting. |

Gemini is an application runtime integration, distinct from the coding assistant.
On 2026-10-29 the candidate supplied a Gemini credential, configured locally
outside Git. Native tool calling and the first three full-corpus investigations
with Gemini 3.5 Flash-Lite succeeded with actual token usage and exact source
validation. The 92-case held-out run is underway; a partial run is not final
evaluation evidence. An optional Ollama adapter exists, but no Ollama deployment
or evaluation is claimed. Actual model IDs and usage remain in generated records.

## What AI drafted or changed

AI assistance covered architecture and implementation planning; Python source
and tests; typed models; prompts and provider integration; custom rank fusion;
parsers/chunking/storage lifecycle behavior; authored synthetic incident records
and evaluation cases; evaluation/benchmark code; the user interface; deployment
configuration; and technical/submission documentation.

The authored incident corpus is synthetic. It is not presented as real incident
evidence. Its answer labels are kept in the evaluation manifest rather than
inserted into the searchable documents. HotpotQA passages retain separate public
dataset provenance and attribution.

## Revisions and checks performed during AI-assisted development

The agents did not merely accept their first generated output. They used actual
tests and source review to revise the implementation. Examples recorded in the
work include preserving model-token chunk tails and title capacity; rejecting
incompatible collection signatures; handling publication-timeout ambiguity;
ensuring repeated batch identities do not hide changed text; rejecting fabricated
citations and secret-bearing provider error bodies; preserving tool-call scope;
bounding upload bodies before multipart parsing; and correcting a mobile table
accessibility element that expanded the viewport.

Later work added atomic, resumable evaluation checkpoints and paced model HTTP
attempts for free-tier runs. Regression tests verify interruption recovery,
retention of failed cases, run-identity mismatch rejection, corpus invalidation,
and reuse of completed comparison configurations without new model calls. These
tests use synthetic/mocked outcomes and do not establish live Gemini success.

Live Gemini testing exposed HTTP 400 rejection of the full nested bounded output
schema. The coding agent checked Google's REST documentation, reproduced the
failure with small synthetic inputs, simplified the wire schema, and retained all
original Pydantic bounds for local output validation. The original failed test
run is retained separately; the corrected run uses a new output folder and
software fingerprint. This protocol fix was informed by a held-out run failure;
it did not change reference labels or tune retrieval thresholds from those labels.

The next live run exposed contradictory verifier explanations and decision flags:
the explanation acknowledged a source conflict while the parsed flag was false.
The schema allowed omission with a false default. The agent made decision fields
mandatory and clarified that reporting a conflict does not resolve the source
disagreement. The separate tuning split is used to check the change before a new
final evaluation. The original 53-case partial run remains unchanged and cannot
be presented as a completed held-out result. Reusing previously inspected test
cases for the later run is regression evidence, not a claim of wholly unseen testing.

A subsequent 45-case run stopped when the model split the two sides of a conflict
into separate objects with one evidence reference each. Local validation rejected
them. The agent verified that Gemini accepts minimum array counts while rejecting
the earlier nested maximum constraints, retained the minimum evidence counts in
the wire schema, and clarified that each conflict must pair both opposing quotes.
A full local-corpus diagnostic then completed synthesis and independent conflict
verification successfully. The previous partial artifacts remain unchanged.

The API/UI was locally exercised with a real embedded Qdrant runtime. Its focused
HTTP tests cover upload/search/source resolution, restart persistence, deletion,
authorization, rate limits, source rendering, streaming validation and metrics.
Manual browser automation additionally checked uploaded markup remained literal
text, a replacement advanced the document revision, and deletion removed the
source. Those are checks performed by AI-operated tools; they are not claims of
independent human review.

## Candidate's independent contribution

The candidate supplied the assignment and the request to plan and implement it,
and chose to configure a Gemini credential and free hosting/database accounts
later, and subsequently supplied Gemini access and signed into GitHub. At this
point, no independently written code changes or independent
manual correctness review by the candidate have been verified in the workspace.
This report therefore does **not** invent a statement that the candidate manually
rewrote modules, independently fixed bugs or reviewed every generated line.

Before submission the candidate should actually read the code, run it, review
sample answers and source citations, make any needed changes, and record those
specific activities here with their dates and commit references. Add only work
that was performed. If no independent code changes were needed, state that
honestly and describe the independent validation instead.

The candidate subsequently created Qdrant Cloud and Render accounts, configured
the deployment, supplied the public URL and management credential, and manually
redeployed commit `5ed377d`. AI-operated HTTP checks verified a real public Gemini
conflict answer, protected document lifecycle and source persistence across that
restart. A full cloud reconciliation checked all 50,085 source records. Browser
automation checked the public desktop/mobile layout without page errors or page
overflow. These are recorded tool observations, not independent human review.

The Gemini 3.5 Flash-Lite run then reached the project's actual 500-request daily
free quota. The partial 25/92-case run remains unchanged, including its provider
error. The agent checked official free-tier pricing and separately verified
all 12 reserved tuning cases with Gemini 3.1 Flash-Lite, then explicitly selected
it for a new 96-case full-cloud test/security run. This does not silently replace a failed response or relabel
the original run as another model. Model-specific runs must keep separate outputs.

After the candidate changed the Render model setting and redeployed `01328c6`,
all three public browser checks completed with fresh Gemini 3.1 responses:
causal answer, conflicting evidence and correct abstention. Cached copies captured
immediately afterward resolved every emitted quote to its actual stored passage.
The agent also recorded 180 hosted process-RSS samples during acceptance; their
maximum was 451.8 MiB. These samples can miss shorter peaks and do not measure
the whole container. Neither this check nor the tuning split substitutes for the
complete test/security evaluation and configuration comparisons.

## Remaining review and external work

Do not represent the following as completed until their evidence is available:

- Real Gemini investigations and the final category-level evaluation. A named
  human's claim/citation entailment review is recommended and remains unverified.
- Any model-comparison or large-corpus performance result not present in the
  generated artifacts with its exact configuration and corpus counts.
- Independent candidate practice of code explanation, debugging and feature
  changes without AI, as required for the practical interview.

The [requirements matrix](REQUIREMENTS.md), [evaluation methodology](EVALUATION_METHODOLOGY.md)
and [interview guide](INTERVIEW_GUIDE.md) describe the evidence needed for these
steps. Do not replace missing evidence with an AI-authored claim of completion.

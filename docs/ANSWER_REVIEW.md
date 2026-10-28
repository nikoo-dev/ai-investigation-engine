# Semantic answer review

Token overlap is useful for regression tests, but cannot tell whether an answer reverses a causal claim, mixes entities, ignores a contradiction or cites a passage that does not support its claim. Use the optional model judge and a recorded human review to examine those failure modes. Neither process changes the source evaluation predictions or the indexed corpus.

## Optional model judge

The `judge_report(settings, report_path, output_dir, limit=None)` function in `investigation.judge` reviews saved evaluation answers with a real configured Gemini or Ollama model. The CLI exposes this as a separate opt-in command; it is never part of ingestion, query serving or the default evaluation run. Extractive mode is rejected as a judge.

The judge receives only the case question, reference answers/facts, expected decision, original candidate answer, claim/citation links and saved cited source quotes. Application settings, credentials, original reasoning traces and hidden prompts are excluded by an explicit field allowlist. All submitted text is marked as evaluation data. The judge has no search tools, does not fetch links and does not open the vector database.

Each case receives four scores from 0 to 1 and a concrete explanation:

| Score | Question the reviewer must answer |
| --- | --- |
| Correctness | Does the answer agree with the reference facts, including entity, date, negation, values and expected answer/abstention/conflict decision? |
| Groundedness | Are all factual additions supported by the provided source quotations? Reference answers are labels, not extra evidence. |
| Citation support | Do the cited quotes entail their attached claims, rather than merely mentioning the same topic? |
| Reasoning completeness | Are all requested parts and reasoning links established, with causation distinguished from correlation? |

A justified abstention can earn full scores for an unanswerable case. An unnecessary abstention on an answerable case loses correctness and completeness. A conflict case must surface both source alternatives and refrain from selecting an unsupported winner. Prompt-injection judgments cover observable output only; mutation prevention is verified by integration tests.

The command writes `judge-results.json` and `judge-report.md` into a new output folder. It records the source report SHA-256, evaluation manifest hash, model/provider, per-case judgments, usage, errors and denominators. Existing judge outputs are not overwritten. There is at most one structured model request per eligible case, with the configured bounded retries, a maximum of 500 selected cases, and a 100,000-character per-case input bound. `limit` selects the first N saved cases in their original order; it is a convenience sample, not an unbiased stratified sample.

Source runtime failures and judge failures receive zero credit in all-selected-case means. Successful-only means are shown separately with their smaller denominators. Failure bodies are not copied into review artifacts. If the original run used source-excerpt answers or test hash embeddings, the report states that semantic judging does not make it a real LLM/semantic-search run.

Model judges can prefer their own style and repeat their own mistakes. The report explicitly flags use of the same model/provider for generation and judging. Prefer a different judge model when available, compare its explanation with source evidence, and retain human review. The judge sees saved quotes rather than the full corpus: it cannot verify that a quote exists in storage, identify every missing retrieval source or prove that a tool side effect did not occur. Keep deterministic citation validation and security tests alongside this report.

No real-provider score is claimed until this command has actually run with that provider. Mocked judge tests validate interfaces and accounting only.

## Human review record

Choose at least five test cases per question category, plus every detected conflict and every automated citation-validation failure. Record the sample-selection method and case IDs before reviewing. Keep tuning and test cases distinct. Open each cited stored passage, check its document revision and exact quote, then assess whether it entails the attached claim. For multi-hop answers, follow the complete source chain and look for an omitted link or unsupported causal inference.

Complete this record for each reviewed run:

- Reviewer and review date:
- Evaluation configuration and report SHA-256:
- Corpus revision and evaluation manifest SHA-256:
- Selection method and selected test case IDs:
- Judge model/provider, if used, and whether it matches generation:

| Case ID / category | Expected and actual decision | Correctness / grounding / citation support / completeness (0-1) | Exact claim and source-passage check | Error cause and improvement |
| --- | --- | --- | --- | --- |
| Fill from a saved prediction | Record both statuses | Give each of the four scores | Cite passage ID, revision, quote, and whether it entails the claim | Attribute to retrieval, synthesis, verification, labels or evaluation |

Record disagreements with the model judge explicitly; do not edit predictions or replace model scores silently. Corrections to labels require a versioned evaluation manifest and a new run. Changes informed by test failures must be disclosed, and subsequent unbiased quality claims require newly held-out cases.

# Optional semantic answer review

Recorded: 2026-10-29T00:40:46.822051+00:00

Judge: `gemini/gemini-3.8-flash`. Source report SHA-256: `8f7cfdbfc0f34abc177c657151e10257ae4706e65581d16f1bcb2fc2ef3e2b7c`.

Selected: 1; judged: 1; errors: 0; unselected: 11.

Same model as generation: `False`. Source preview/hash mode: `False`.

Metric | All selected cases (errors score 0) | Successful judgments only
--- | ---: | ---:
correctness | 1.0000 | 1.0000
groundedness | 1.0000 | 1.0000
citation_support | 1.0000 | 1.0000
reasoning_completeness | 1.0000 | 1.0000

Denominators: `{'all_selected_case_means': 1, 'successful_judgment_means': 1}`. Provider usage: `{'input_tokens': 1392, 'output_tokens': 876, 'calls': 1, 'retries': 0, 'reasoning_tokens': 758}`.

## Per-case judgments

- `cause-13`: correctness=1.000, groundedness=1.000, citation_support=1.000, reasoning_completeness=1.000. The candidate answer accurately answers all parts of the prompt: system change CHG-013, the affected authorization-service, and the confirmation via controlled replay and rollback. All claims are fully grounded and directly entailed by the cited quotes [C1], [C2], and [C3].

## Interpretation limits

- Model scores are fallible semantic judgments, not ground truth; retain manual source review.
- The judge sees saved cited quotes, not the full corpus. It cannot verify quote existence, retrieval coverage or tool side effects.
- Using the same model for generation and judging can create correlated errors and self-preference; use a different judge model and human review where possible.
- All selected cases, including source/runtime/judge errors, remain in all-case score denominators with zero credit. Successful-only means exclude failures and must be labeled.
- No engine, index or document collection is opened or mutated by judging. Original predictions remain unchanged.

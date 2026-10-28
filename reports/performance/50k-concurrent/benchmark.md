# Performance benchmark

Recorded: 2026-10-27T14:58:49.726654+00:00

Corpus: `{'documents': 50085, 'chunks': 52243, 'corpus_revision': '9e48a0b3-7f60-483b-86d9-5e7149562bb6', 'backend': 'qdrant_local'}`. Provider: `extractive`.

Requests: 20 at concurrency 2; errors: 0.

p50: 2482.9 ms; p95: 2730.7 ms; throughput: 0.782 requests/s.

Sampled peak process RSS: 2276.6 MiB.

Limitations:

- RSS is sampled every 25 ms and can miss shorter transient peaks; external Qdrant-server RSS is not included.
- Local/client mode may use exact vector scans. Report server mode separately before extrapolating scale.
- A run with fewer than 50,000 stored documents is a small-corpus benchmark, not evidence of 50,000-record performance.

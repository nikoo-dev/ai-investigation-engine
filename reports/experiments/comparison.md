# Configuration comparison

All configurations use the same evaluation manifest. Different chunk/model experiments require separate compatible indexes; never mix vectors from different models.

Configuration | Recall@10 | All-support@10 | MRR | Token F1 | Citation gold precision | Status | p95 ms
--- | ---: | ---: | ---: | ---: | ---: | ---: | ---:
minilm-structure-hybrid-rerank | 0.9321 | 0.8148 | 1.0000 | 0.0951 | 0.5257 | 0.8587 | 2182.2042
minilm-fixed-hybrid-rerank | 0.9321 | 0.8148 | 1.0000 | 0.0951 | 0.5257 | 0.8587 | 1752.4417
minilm-structure-dense-rerank | 0.9321 | 0.8148 | 1.0000 | 0.0920 | 0.5060 | 0.8152 | 1459.5323
minilm-structure-hybrid-no-rerank | 0.9691 | 0.9259 | 1.0000 | 0.0647 | 0.3393 | 0.5652 | 159.2940
bge-small-structure-hybrid-rerank | 0.9321 | 0.8148 | 1.0000 | 0.0948 | 0.5198 | 0.8587 | 2451.5947

Compare quality with latency and resource cost. Do not select a winner solely on a metric whose applicable case count is small. See each configuration's per-category and failure analysis before making a deployment choice.

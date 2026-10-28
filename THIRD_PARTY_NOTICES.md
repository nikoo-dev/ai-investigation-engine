# Third-party data and models

The source code is authored for the assignment. Third-party materials retain their
own licenses; this file does not relicense upstream documents or model weights.

- **HotpotQA**: Yang et al., *HotpotQA: A Dataset for Diverse, Explainable Multi-hop
  Question Answering* (2018), <https://arxiv.org/abs/1809.09600>. Dataset mirror:
  <https://huggingface.co/datasets/hotpotqa/hotpot_qa>, pinned revision
  `1908d6afbbead072334abe2965f91bd2709910ab`, dataset card CC-BY-SA-4.0.
  Wikipedia-derived passages retain source titles/URLs and dataset provenance.
  Subsets normalize text, deduplicate complete passages, and select records by a
  documented deterministic algorithm; these are transformations of upstream data.
- **Authored incident fixture**: synthetic change logs, incidents, catalogs,
  conflicting exports and attack probes are marked `synthetic=true`; CC0-1.0.
- **sentence-transformers/all-MiniLM-L6-v2**: Apache-2.0, ONNX model source
  <https://huggingface.co/Qdrant/all-MiniLM-L6-v2-onnx>.
- **BAAI/bge-small-en-v1.5** (optional comparison): MIT,
  <https://huggingface.co/BAAI/bge-small-en-v1.5>.
- **Xenova/ms-marco-MiniLM-L-6-v2** cross-encoder: Apache-2.0,
  <https://huggingface.co/Xenova/ms-marco-MiniLM-L-6-v2>.
- **Qdrant**, **FastEmbed**, **FastAPI**, and other dependencies: see the exact
  locked package versions and their distributed license files in `uv.lock` and
  installed distributions. Downloaded model weights and raw datasets are not
  bundled into the source repository.

Gemini is an external service governed by Google's API terms. Free-tier data-use
and quota policies must be reviewed before uploading documents.

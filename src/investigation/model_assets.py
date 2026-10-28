"""Immutable revisions for the models used in the submitted experiments.

Changing a pin is an embedding-pipeline migration: bump the cache/collection
signature and reindex, rather than silently mixing old and new model vectors.
"""

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelAsset:
    repository: str
    revision: str
    weights: str


MODEL_ASSETS = {
    "sentence-transformers/all-MiniLM-L6-v2": ModelAsset(
        "Qdrant/all-MiniLM-L6-v2-onnx", "d13954661f83248295ba75c1ed411eef3b7b936e", "model.onnx"
    ),
    "BAAI/bge-small-en-v1.5": ModelAsset(
        "Qdrant/bge-small-en-v1.5-onnx-Q",
        "aa8f8b060edb00e03bfdd08813a2949946c8ba55",
        "model_optimized.onnx",
    ),
    "Xenova/ms-marco-MiniLM-L-6-v2": ModelAsset(
        "Xenova/ms-marco-MiniLM-L-6-v2",
        "a09144355adeed5f58c8ed011d209bf8ee5a1fec",
        "onnx/model.onnx",
    ),
}


def pinned_model_path(model_name: str, cache_dir: Path) -> str | None:
    asset = MODEL_ASSETS.get(model_name)
    if asset is None:
        return None  # Custom models retain FastEmbed's registry behavior; disclose their version.
    directory = (
        cache_dir
        / ("models--" + asset.repository.replace("/", "--"))
        / "snapshots"
        / asset.revision
    )
    files = [
        asset.weights,
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
    ]
    if all((directory / filename).is_file() for filename in files):
        return str(directory)
    from huggingface_hub import snapshot_download

    return snapshot_download(
        repo_id=asset.repository,
        revision=asset.revision,
        cache_dir=str(cache_dir),
        allow_patterns=files,
    )


def model_provenance(cache_dir: Path) -> list[dict]:
    from investigation.datasets import file_sha256

    result = []
    for name, asset in MODEL_ASSETS.items():
        resolved = pinned_model_path(name, cache_dir)
        assert resolved is not None
        directory = Path(resolved)
        result.append(
            {
                "model": name,
                **asdict(asset),
                "files": {
                    str(path.relative_to(directory)).replace("\\", "/"): {
                        "sha256": file_sha256(path),
                        "bytes": path.stat().st_size,
                    }
                    for path in directory.rglob("*")
                    if path.is_file()
                },
            }
        )
    return result

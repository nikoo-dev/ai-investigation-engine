from investigation.model_assets import MODEL_ASSETS, pinned_model_path


def test_known_models_load_exact_cached_revision_without_network(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("A complete pinned snapshot must load offline")

    monkeypatch.setattr("huggingface_hub.snapshot_download", forbidden)
    for name, asset in MODEL_ASSETS.items():
        directory = (
            tmp_path
            / ("models--" + asset.repository.replace("/", "--"))
            / "snapshots"
            / asset.revision
        )
        for filename in [
            asset.weights,
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
        ]:
            path = directory / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic asset fixture")
        assert pinned_model_path(name, tmp_path) == str(directory)


def test_missing_snapshot_downloads_immutable_revision_and_only_required_files(
    tmp_path, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        "huggingface_hub.snapshot_download", lambda **kwargs: calls.append(kwargs) or "snapshot"
    )
    asset = MODEL_ASSETS["BAAI/bge-small-en-v1.5"]
    assert pinned_model_path("BAAI/bge-small-en-v1.5", tmp_path) == "snapshot"
    assert calls[0]["revision"] == asset.revision
    assert asset.weights in calls[0]["allow_patterns"]
    assert pinned_model_path("custom/unregistered-here", tmp_path) is None

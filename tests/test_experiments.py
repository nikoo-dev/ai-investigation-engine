import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from investigation.config import Settings
from investigation.evaluation import EvaluationCase
from investigation.experiments import (
    experiment_configs,
    run_experiments,
    select_experiment_records,
)


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def records(count=12):
    return [
        {
            "id": f"doc-{index}",
            "title": f"Source {index}",
            "text": f"An independent source fact number {index}.",
            "metadata": {"dataset": "fixture"},
        }
        for index in range(count)
    ]


def case(identity="test-case", source="doc-11", split="test"):
    return EvaluationCase(
        id=identity,
        category="direct",
        question="What fact is supported?",
        expected_answers=["fact"],
        gold_document_ids=[source],
        split=split,
    )


def test_selection_is_order_independent_and_forces_all_gold_sources(tmp_path):
    rows = records()
    first = write_jsonl(tmp_path / "one.jsonl", rows)
    second = write_jsonl(tmp_path / "two.jsonl", reversed(rows))
    cases = [case(source="doc-11"), case("another", "doc-10")]
    selected, manifest = select_experiment_records(first, cases, minimum_records=5, seed=7)
    reversed_selected, reversed_manifest = select_experiment_records(
        second, cases, minimum_records=5, seed=7
    )
    assert selected == reversed_selected
    assert len(selected) == 5
    assert {"doc-10", "doc-11"} <= set(manifest["selected_ids"])
    assert manifest["forced_gold_sources"] == 2
    assert manifest["distractor_sources"] == 3
    assert manifest["selected_records_sha256"] == reversed_manifest["selected_records_sha256"]
    assert manifest["source_corpus_sha256"] != reversed_manifest["source_corpus_sha256"]


def test_more_gold_sources_than_minimum_are_all_retained(tmp_path):
    source = write_jsonl(tmp_path / "corpus.jsonl", records())
    cases = [case(f"case-{index}", f"doc-{index}") for index in range(4)]
    selected, manifest = select_experiment_records(source, cases, minimum_records=2)
    assert len(selected) == 4
    assert manifest["distractor_sources"] == 0


@pytest.mark.parametrize("problem", ["missing-gold", "too-small", "conflicting-id"])
def test_selection_rejects_invalid_comparisons(tmp_path, problem):
    rows = records(3)
    questions = [case(source="doc-0")]
    minimum = 2
    if problem == "missing-gold":
        questions = [case(source="missing")]
    elif problem == "too-small":
        minimum = 10
    else:
        rows.append({**rows[0], "text": "Conflicting content for the same ID."})
    source = write_jsonl(tmp_path / "corpus.jsonl", rows)
    with pytest.raises(ValueError):
        select_experiment_records(source, questions, minimum)


def test_matrix_changes_one_factor_at_a_time():
    configs = experiment_configs()
    assert len(configs) == 5
    baseline = configs[0]
    fields = [
        "embedding_model",
        "embedding_dimension",
        "chunk_strategy",
        "retrieval_mode",
        "reranker_enabled",
    ]
    for config in configs[1:]:
        assert sum(getattr(config, field) != getattr(baseline, field) for field in fields) == 1
    assert len(experiment_configs(False)) == 4


def install_fake_runtime(monkeypatch, main_directory, fail_ingestion=False):
    # This fixture exercises isolation/reporting only. It never pretends to be a
    # real model result outside this test's temporary directory.
    import investigation.experiments as module

    runtimes = []
    evaluations = []

    class FakeStore:
        count = 0

        def stats(self):
            return {"documents": self.count, "chunks": self.count, "corpus_revision": "fixture"}

    class FakeRuntime:
        def __init__(self, settings, cache_settings):
            assert settings.qdrant_url is None
            assert settings.qdrant_api_key is None
            assert settings.data_dir != main_directory
            assert cache_settings.data_dir == main_directory
            assert all(previous.closed for previous in runtimes)
            self.settings = settings
            self.store = FakeStore()
            self.closed = False
            self.embedder = SimpleNamespace(
                fingerprint=f"fastembed:{settings.embedding_model}:fixture"
            )
            self.ingestion = SimpleNamespace(ingest_records=self.ingest)
            self.engine = SimpleNamespace(settings=settings, store=self.store)
            runtimes.append(self)

        def ingest(self, source_records, batch_size):
            self.store.count = len(source_records)
            assert batch_size > 0
            return {"created": len(source_records), "duplicates": 0, "failed": int(fail_ingestion)}

        def close(self):
            self.closed = True

    def fake_evaluate(engine, cases, output_dir, name):
        evaluations.append((name, [question.id for question in cases]))
        digest = hashlib.sha256(
            "\n".join(question.model_dump_json() for question in cases).encode()
        ).hexdigest()
        report = {
            "configuration": name,
            "evaluation_sha256": digest,
            "aggregate": {"recall_at_10": 0.5, "error_rate": 0.0},
            "by_source": {},
            "by_split": {},
            "rows": [
                {
                    "answer": {
                        "provider": "extractive",
                        "model": "extractive",
                        "usage": {"input_tokens": 4},
                    }
                }
            ],
        }
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        (Path(output_dir) / "results.json").write_text(json.dumps(report), encoding="utf-8")
        return report

    monkeypatch.setattr(module, "_build_experiment_runtime", FakeRuntime)
    monkeypatch.setattr(module, "evaluate", fake_evaluate)
    return runtimes, evaluations


def test_runner_isolates_indexes_closes_runtimes_and_records_exact_configuration(
    tmp_path, monkeypatch
):
    corpus = write_jsonl(tmp_path / "corpus.jsonl", records())
    cases = write_jsonl(
        tmp_path / "cases.jsonl",
        [
            case().model_dump(),
            case("security-case", "doc-10", "security").model_dump(),
            case("tuning-case", "doc-9", "tuning").model_dump(),
        ],
    )
    main_dir = tmp_path / "main"
    settings = Settings(
        _env_file=None,
        data_dir=main_dir,
        embedding_backend="fastembed",
        qdrant_url="https://unused-cloud.invalid",
        llm_provider="extractive",
    )
    runtimes, evaluations = install_fake_runtime(monkeypatch, main_dir)
    output = tmp_path / "reports"
    result = run_experiments(
        settings, corpus, cases, output, minimum_records=5, index_root=tmp_path / "indexes"
    )
    assert result["status"] == "complete"
    assert result["case_count"] == 2
    assert result["split_counts"] == {"test": 1, "security": 1}
    assert len(result["configurations"]) == 5
    assert len(evaluations) == 5
    assert all(ids == ["test-case", "security-case"] for _, ids in evaluations)
    assert all(runtime.closed for runtime in runtimes)
    assert runtimes[0].settings.data_dir == runtimes[2].settings.data_dir
    assert runtimes[0].settings.data_dir != runtimes[1].settings.data_dir
    assert runtimes[0].settings.data_dir != runtimes[-1].settings.data_dir
    assert not (main_dir / "qdrant").exists()
    assert (output / "selection.json").exists()
    assert (output / "comparison.md").exists()
    assert (output / "summary.md").exists()
    first = result["configurations"][0]
    assert first["actual_providers"] == {"extractive": 1}
    assert first["usage_totals"]["input_tokens"] == 4
    assert first["corpus_stats"]["documents"] == 5
    assert "tuning-case" not in result["case_ids"]


def test_runner_closes_runtime_and_records_failure_without_inventing_results(tmp_path, monkeypatch):
    corpus = write_jsonl(tmp_path / "corpus.jsonl", records())
    cases = write_jsonl(tmp_path / "cases.jsonl", [case().model_dump()])
    settings = Settings(_env_file=None, data_dir=tmp_path / "main", embedding_backend="fastembed")
    runtimes, evaluations = install_fake_runtime(
        monkeypatch, settings.data_dir, fail_ingestion=True
    )
    output = tmp_path / "reports"
    with pytest.raises(ValueError, match="Indexed independent record count"):
        run_experiments(
            settings, corpus, cases, output, minimum_records=5, index_root=tmp_path / "indexes"
        )
    saved = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert saved["status"] == "failed"
    assert saved["configurations"] == []
    assert saved["error_type"] == "ValueError"
    assert runtimes[0].closed
    assert not evaluations


def test_runner_refuses_to_label_hash_fixtures_as_semantic(tmp_path):
    with pytest.raises(ValueError, match="hash fixtures"):
        run_experiments(
            Settings(_env_file=None, embedding_backend="hash"),
            tmp_path / "missing-corpus",
            tmp_path / "missing-cases",
            tmp_path / "reports",
        )

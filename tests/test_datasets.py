import json

import pytest

from investigation.datasets import (
    HOTPOT_REVISION,
    build_hotpot_subset,
    content_hash,
    hotpot_record,
    read_jsonl,
    seed_cases,
    seed_records,
    write_seed,
)


def hotpot_row(identity, kind="bridge"):
    return {
        "id": identity,
        "question": f"What city belongs to {identity}?",
        "answer": "Tbilisi",
        "type": kind,
        "context": {
            "title": [f"{identity} Person", f"{identity} Place"],
            "sentences": [
                [f"{identity} Person was born in Tbilisi. This passage identifies a person."],
                [f"{identity} Place is located in Georgia. This passage identifies a place."],
            ],
        },
        "supporting_facts": {
            "title": [f"{identity} Person", f"{identity} Place"],
            "sent_id": [0, 0],
        },
    }


def test_seed_has_meaningful_independent_records_and_balanced_questions():
    records, cases = seed_records(), seed_cases()
    assert len(records) >= 50
    assert len(cases) >= 60
    assert len({record["id"] for record in records}) == len(records)
    assert len({content_hash(record["text"]) for record in records}) == len(records)
    assert all(record["source_uri"] and record["metadata"]["synthetic"] for record in records)
    expected = {
        "direct",
        "comparison",
        "multi_hop",
        "unanswerable",
        "contradictory",
        "prompt_injection",
    }
    assert {case.category for case in cases} == expected
    corpus_ids = {record["id"] for record in records}
    assert all(set(case.gold_document_ids) <= corpus_ids for case in cases)
    assert all(len(case.gold_document_ids) > 1 for case in cases if case.category == "multi_hop")
    test_sources = {doc for case in cases if case.split == "test" for doc in case.gold_document_ids}
    tuning_sources = {
        doc for case in cases if case.split == "tuning" for doc in case.gold_document_ids
    }
    assert tuning_sources and not (test_sources & tuning_sources)
    corpus = " ".join(record["text"] for record in records)
    assert all(case.question not in corpus for case in cases)


def test_seed_generation_is_byte_reproducible(tmp_path):
    first = write_seed(tmp_path / "one")
    second = write_seed(tmp_path / "two")
    assert first == second
    assert list(read_jsonl(tmp_path / "one" / "corpus.jsonl")) == seed_records()
    assert first["category_counts"]["contradictory"] >= 10


def test_hotpot_subset_preserves_validation_evidence_without_qa_leakage():
    validation = [hotpot_row("heldout1"), hotpot_row("heldout2", "comparison")]
    train = [hotpot_row(f"train{i}") for i in range(20)]
    records, cases = build_hotpot_subset(
        train, validation, minimum_records=12, seed=9, max_eval_questions=2
    )
    assert len(records) == 12
    assert len(cases) == 2
    assert {case.category for case in cases} == {"multi_hop", "comparison"}
    ids = {record["id"] for record in records}
    assert all(set(case.gold_document_ids) <= ids for case in cases)
    assert all("question" not in record and "answer" not in record for record in records)
    assert all("supporting_facts" not in record["metadata"] for record in records)
    assert all(record["metadata"]["dataset_revision"] == HOTPOT_REVISION for record in records)
    assert (records, cases) == build_hotpot_subset(train, validation, 12, 9, 2)


def test_hotpot_deduplicates_by_normalized_content_not_qa_count():
    duplicate_rows = [hotpot_row("same") for _ in range(100)]
    with pytest.raises(ValueError, match="distinct source passages"):
        build_hotpot_subset(duplicate_rows, [], minimum_records=3, max_eval_questions=0)
    assert content_hash("Alpha  beta\nGamma") == content_hash("alpha beta gamma")


def test_missing_supporting_context_fails_instead_of_silently_scoring_bad_labels():
    row = hotpot_row("heldout")
    row["supporting_facts"]["title"].append("Absent page")
    row["supporting_facts"]["sent_id"].append(0)
    with pytest.raises(ValueError, match="missing supporting context"):
        build_hotpot_subset([], [row], minimum_records=2, max_eval_questions=1)


def test_source_uri_encoded_and_identity_content_stable():
    one = hotpot_record("A page / with spaces", ["A long article sentence."], "row1", "train")
    two = hotpot_record("Another title", ["A long article sentence."], "row2", "validation")
    assert one["id"] == two["id"]
    assert "%2F" in one["source_uri"]


def test_jsonl_error_has_source_line(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps({"ok": 1}) + "\n[1, 2]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bad.jsonl:2"):
        list(read_jsonl(path))

"""Reconcile independent source records with the active persisted corpus."""

import time
from pathlib import Path

from investigation.datasets import file_sha256, read_jsonl
from investigation.ingestion import content_checksum
from investigation.models import utc_now
from investigation.parsers import normalize_text
from investigation.storage import point_id


def reconcile_corpus(store, corpus_path: Path, batch_size: int = 256) -> dict:
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be in 1..1000")
    started = time.perf_counter()
    counts = {
        "records_checked": 0,
        "missing": 0,
        "checksum_mismatches": 0,
        "source_uri_mismatches": 0,
        "duplicate_source_ids": 0,
    }
    examples: list[dict] = []
    seen = set()
    batch = []

    def check(rows):
        identities = [point_id(str(row["id"])) for row in rows]
        documents = store.get_documents(identities)
        for identity, record in zip(identities, rows, strict=True):
            counts["records_checked"] += 1
            if identity in seen:
                counts["duplicate_source_ids"] += 1
            seen.add(identity)
            document = documents.get(identity)
            failures = []
            if not document or document.status != "ready":
                counts["missing"] += 1
                failures.append("missing_or_not_ready")
            else:
                expected = content_checksum(normalize_text(record["text"]))
                if document.checksum != expected or content_checksum(document.text) != expected:
                    counts["checksum_mismatches"] += 1
                    failures.append("checksum")
                if document.source_uri != record.get("source_uri"):
                    counts["source_uri_mismatches"] += 1
                    failures.append("source_uri")
            if failures and len(examples) < 20:
                examples.append({"id": identity, "failures": failures})

    for record in read_jsonl(corpus_path):
        batch.append(record)
        if len(batch) >= batch_size:
            check(batch)
            batch = []
    if batch:
        check(batch)
    stats = store.stats()
    passed = (
        counts["records_checked"] >= 50000
        and stats["documents"] >= 50000
        and not any(value for key, value in counts.items() if key != "records_checked")
    )
    return {
        "status": "pass" if passed else "incomplete",
        "checked_at": utc_now(),
        "corpus_sha256": file_sha256(corpus_path),
        "unique_source_ids": len(seen),
        **counts,
        "store": stats,
        "failure_examples": examples,
        "elapsed_seconds": time.perf_counter() - started,
    }

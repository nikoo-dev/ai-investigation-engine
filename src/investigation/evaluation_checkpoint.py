"""Atomic evaluation checkpoints bound to cases, configuration, code and corpus.

One writer owns an output directory. The digest detects accidental corruption;
it is not an attestation that predictions came from an external model.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from investigation.models import utc_now


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def software_fingerprint() -> str:
    directory = Path(__file__).parent
    return canonical_digest(
        {
            path.relative_to(directory).as_posix(): hashlib.sha256(
                path.read_text(encoding="utf-8").encode("utf-8")
            ).hexdigest()
            for path in sorted(directory.rglob("*.py"))
        }
    )


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


class EvaluationCheckpoint:
    def __init__(self, path: Path, identity: dict, cases: list[dict], resume: bool):
        self.path = path
        self.identity = identity
        self.run_id = str(uuid4())
        self.created_at = utc_now()
        self.elapsed_seconds = 0.0
        self.rows: list[dict] = []
        self.invalidated = False
        if path.exists():
            if not resume:
                raise ValueError(
                    "Evaluation checkpoint exists. Use --resume or a new output directory."
                )
            saved = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(saved, dict):
                raise ValueError("Evaluation checkpoint must contain a JSON object.")
            if saved.get("invalidated"):
                raise ValueError("Cannot resume: the corpus changed during this evaluation.")
            if saved.get("version") != 1 or saved.get("identity") != identity:
                raise ValueError("Cannot resume: cases, configuration, code or corpus changed.")
            rows = saved.get("rows")
            if (
                not isinstance(rows, list)
                or len(rows) > len(cases)
                or saved.get("rows_sha256") != canonical_digest(rows)
                or any(not isinstance(row, dict) for row in rows)
                or [row.get("case") for row in rows] != cases[: len(rows)]
            ):
                raise ValueError(
                    "Evaluation checkpoint rows are corrupt or do not match the case prefix."
                )
            self.rows = rows
            self.run_id = saved["run_id"]
            self.created_at = saved["created_at"]
            self.elapsed_seconds = float(saved["elapsed_seconds"])

    def save(self, elapsed_seconds: float) -> None:
        atomic_json(
            self.path,
            {
                "version": 1,
                "run_id": self.run_id,
                "created_at": self.created_at,
                "updated_at": utc_now(),
                "identity": self.identity,
                "invalidated": self.invalidated,
                "elapsed_seconds": elapsed_seconds,
                "rows_sha256": canonical_digest(self.rows),
                "rows": self.rows,
            },
        )

"""Read-only submission evidence audit; no model initialization or provisioning.

This checks artifacts and live observations, not the authenticity of every past
observation. A report claiming a live model call is still a recorded result, not
cryptographic proof of that call. Missing/preview evidence never becomes success.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
from pydantic import ValidationError

from investigation.evaluation import EvaluationCase
from investigation.models import InvestigationAnswer, utc_now

REQUIRED_DOCUMENTS = (
    "README.md",
    "docs/ARCHITECTURE.md",
    "docs/API.md",
    "docs/DEPLOYMENT.md",
    "docs/EVALUATION_METHODOLOGY.md",
    "docs/AI_USAGE_REPORT.md",
    "docs/REQUIREMENTS.md",
    "docs/INTERVIEW_GUIDE.md",
    "docs/DEMO_SCRIPT.md",
)
REQUIRED_CATEGORIES = {"direct", "comparison", "multi_hop", "unanswerable", "contradictory"}
HEX64 = re.compile(r"[a-f0-9]{64}")


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"Missing or invalid JSON artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact must contain an object: {path.name}")
    return value


def _artifact(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Artifact path is not configured.")
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Submission artifacts must be inside the project directory.")
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Artifact is missing or empty: {path.name}")
    return path


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _public_https(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("A public HTTPS URL is not configured.")
    try:
        parsed = urlparse(value.strip())
        port = parsed.port
    except ValueError as error:
        raise ValueError("The public HTTPS URL is malformed.") from error
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or port not in (None, 443)
    ):
        raise ValueError("Use a public HTTPS URL without credentials, query or fragment.")
    if host in {"localhost", "example.com", "example.org", "example.net"} or host.endswith(
        (".localhost", ".local", ".test", ".invalid", ".example")
    ):
        raise ValueError("Local and placeholder URLs are not public submission evidence.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError("Local/private IP addresses are not public submission URLs.")
    return value.strip().rstrip("/")


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Captured timestamps must be ISO 8601 strings with a timezone.")
    try:
        instant = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Captured timestamps must be valid ISO 8601 values.") from error
    if instant.tzinfo is None:
        raise ValueError("Captured timestamps require an explicit timezone.")
    return instant.astimezone(UTC)


def _dataset(path: Path, root: Path) -> dict[str, Any]:
    manifest = _object(path)
    records = manifest.get("records")
    primary = manifest.get("primary_records", records)
    if type(records) is not int or type(primary) is not int or primary < 50000 or records < primary:
        raise ValueError(
            "Dataset preparation manifest must record at least 50,000 primary source records."
        )
    for key in ("corpus_sha256", "cases_sha256"):
        if not isinstance(manifest.get(key), str) or not HEX64.fullmatch(manifest[key]):
            raise ValueError(
                "Dataset preparation manifest requires valid corpus/case SHA-256 values."
            )
    if not all(
        manifest.get(key) is not None and str(manifest[key]).strip()
        for key in ("revision", "seed", "license", "source_url")
    ):
        raise ValueError("Dataset provenance requires revision, seed, license and source URL.")
    verified = False
    # The committed manifest may be separated from ignored raw corpus artifacts.
    for directory in (path.parent, root / "data/corpus/hotpot"):
        corpus, cases = directory / "corpus.jsonl", directory / "cases.jsonl"
        if corpus.is_file() and cases.is_file():
            if _sha(corpus) != manifest["corpus_sha256"] or _sha(cases) != manifest["cases_sha256"]:
                raise ValueError("Dataset corpus/case hashes do not match its manifest.")
            verified = True
            break
    return {
        "records": records,
        "primary_records": primary,
        "file_hashes_verified": verified,
        "record_count_independently_recounted": False,
        "corpus_sha256": manifest["corpus_sha256"],
        "cases_sha256": manifest["cases_sha256"],
        "revision": manifest["revision"],
    }


def _evaluation(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    report = _object(path)
    rows = report.get("rows")
    if not isinstance(rows, list) or report.get("case_count") != len(rows):
        raise ValueError(
            "Evaluation case_count must match retained per-case rows, including failures."
        )
    settings = report.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError("Evaluation settings must be an object.")
    if settings.get("embedding_backend") != "fastembed" or settings.get("llm_provider") not in {
        "gemini",
        "ollama",
    }:
        raise ValueError(
            "Final evaluation requires real semantic embeddings and Gemini/Ollama; extractive/hash runs are previews."
        )
    cases, identifiers = [], set()
    counts: Counter[str] = Counter()
    errors, live_tests = 0, 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each evaluation row must retain its case and outcome.")
        try:
            case = EvaluationCase.model_validate(row.get("case"))
        except ValidationError as error:
            raise ValueError("Evaluation contains an invalid test case.") from error
        if case.id in identifiers:
            raise ValueError("Repeated question IDs cannot inflate evaluation case counts.")
        identifiers.add(case.id)
        cases.append(case)
        if case.split == "test":
            counts[case.category] += 1
        if row.get("error") or row.get("answer") is None:
            errors += 1
            continue
        try:
            answer = InvestigationAnswer.model_validate(row["answer"])
        except ValidationError as error:
            raise ValueError("Evaluation contains an invalid answer record.") from error
        if answer.status == "error":
            errors += 1
            continue
        calls = answer.usage.get("calls")
        if (
            answer.provider != settings["llm_provider"]
            or answer.provider not in {"gemini", "ollama"}
            or re.search(
                r"(?:^|[-_/:\s])(test|fake|mock|simulated|extractive|unavailable|source-excerpts)(?:$|[-_/:\s])",
                answer.model,
                re.I,
            )
            or not answer.model.strip()
            or answer.model != settings.get("llm_model")
            or answer.cached
            or isinstance(calls, bool)
            or not isinstance(calls, (float, int))
            or not math.isfinite(calls)
            or calls <= 0
        ):
            raise ValueError(
                "Successful evaluation rows must record uncached real-provider calls and the configured model."
            )
        if case.split == "test":
            live_tests += 1
    digest = hashlib.sha256(
        "\n".join(case.model_dump_json() for case in cases).encode()
    ).hexdigest()
    if report.get("evaluation_sha256") != digest:
        raise ValueError("Evaluation case-manifest hash does not match its retained rows.")
    aggregate = report.get("aggregate", {})
    if not isinstance(aggregate, dict):
        raise ValueError("Evaluation aggregate metrics must be an object.")
    metrics = ("recall_at_10", "mrr", "answer_token_f1", "citation_source_validity", "error_rate")
    if any(
        not isinstance(aggregate.get(key), (int, float)) or not math.isfinite(aggregate[key])
        for key in metrics
    ):
        raise ValueError(
            "Evaluation is missing finite retrieval, answer, citation or error metrics."
        )
    if rows and not math.isclose(aggregate["error_rate"], errors / len(rows), abs_tol=1e-9):
        raise ValueError("Evaluation error rate does not match retained failures.")
    evidence = {
        "case_count": len(cases),
        "test_cases": sum(counts.values()),
        "live_test_cases": live_tests,
        "test_categories": dict(counts),
        "errors": errors,
        "evaluation_sha256": digest,
        "file_sha256": _sha(path),
        "provider": settings["llm_provider"],
        "model": settings.get("llm_model"),
    }
    if errors or live_tests < 40 or not REQUIRED_CATEGORIES <= set(counts):
        raise ValueError(
            f"Final evaluation needs 40+ completed live test cases covering required categories; recorded live={live_tests}, errors={errors}, categories={sorted(counts)}."
        )
    return report, evidence


def audit_submission(
    project_root: Path, manifest_path: Path, store: Any = None, check_urls: bool = False
) -> dict[str, Any]:
    """Inspect every submission gate and return a JSON-serializable audit.

    This function never opens a Qdrant directory or initializes a model. The caller
    may inject an already-open Store; absent a Store, current corpus state is not
    verified. Network GETs occur only with check_urls=True, with 5-second timeouts
    and redirects disabled. Missing evidence returns incomplete rather than raising.
    """
    root = Path(project_root).resolve()
    checks: list[dict[str, Any]] = []

    def add(
        identity: str,
        passed: bool,
        detail: str,
        evidence: Any = None,
        level: str = "verified",
        required: bool = True,
    ) -> None:
        checks.append(
            {
                "id": identity,
                "status": "pass" if passed else "incomplete",
                "detail": detail,
                "evidence_level": level if passed else "unverified",
                "evidence": evidence or {},
                "required": required,
            }
        )

    try:
        manifest = _object(_artifact(root, str(manifest_path)))
        add("submission_manifest", True, "Submission manifest is readable.")
    except (ValueError, OSError) as error:
        manifest = {}
        add("submission_manifest", False, str(error))

    missing_docs = [
        name
        for name in REQUIRED_DOCUMENTS
        if not (root / name).is_file() or (root / name).stat().st_size == 0
    ]
    add(
        "documentation",
        not missing_docs,
        "Required project documents exist."
        if not missing_docs
        else "Required project documents are missing or empty.",
        {"missing": missing_docs},
    )

    commit = None
    try:
        git = ["git", "-c", f"safe.directory={root}", "-C", str(root)]
        result = subprocess.run(
            [*git, "log", "-1", "--format=%H"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        top = subprocess.run(
            [*git, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if (
            result.returncode == 0
            and top.returncode == 0
            and Path(top.stdout.strip()).resolve() == root
            and re.fullmatch(r"[a-f0-9]{40,64}", result.stdout.strip())
        ):
            commit = result.stdout.strip()
        add(
            "git_history",
            bool(commit),
            "A local committed history exists."
            if commit
            else "No committed Git history could be verified.",
            {"commit": commit},
        )
    except (OSError, subprocess.TimeoutExpired):
        add("git_history", False, "Git history could not be inspected.")

    try:
        evidence = _dataset(_artifact(root, manifest.get("dataset_manifest")), root)
        add(
            "dataset_manifest",
            True,
            "Preparation manifest records 50,000+ primary records with hashes/provenance. Actual corpus file verification is reported separately.",
            evidence,
            "preparation_manifest",
        )
    except (ValueError, OSError, UnicodeError) as error:
        add("dataset_manifest", False, str(error))

    try:
        if store is None:
            raise ValueError(
                "Current active corpus not verified: no Store was supplied. A reported file count is not a database count."
            )
        stats = store.stats()
        count = stats.get("documents")
        passed = isinstance(count, int) and not isinstance(count, bool) and count >= 50000
        add(
            "active_corpus",
            passed,
            "Current Store reports at least 50,000 active documents."
            if passed
            else "Current Store has fewer than 50,000 verified active documents.",
            {
                key: stats[key]
                for key in ("documents", "chunks", "corpus_revision", "backend")
                if key in stats
            },
        )
    except Exception as error:
        add(
            "active_corpus",
            False,
            str(error) if store is None else f"Store inspection failed ({type(error).__name__}).",
        )

    report = None
    evaluation_evidence: dict[str, Any] = {}
    try:
        report, evaluation_evidence = _evaluation(
            _artifact(root, manifest.get("evaluation_report"))
        )
        add(
            "live_llm_evaluation",
            True,
            "Retained report records 40+ real-provider test outcomes with required metrics/categories and no runtime failures.",
            evaluation_evidence,
            "recorded_run",
        )
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as error:
        add("live_llm_evaluation", False, str(error))

    try:
        if report is None:
            raise ValueError("A valid final evaluation is needed before comparing configurations.")
        paths = manifest.get("comparison_reports", [])
        if not isinstance(paths, list) or not paths:
            raise ValueError("comparison_reports must name measured configuration result files.")
        comparisons = [report]
        for value in paths:
            other, _ = _evaluation(_artifact(root, value))
            if other["evaluation_sha256"] != report["evaluation_sha256"]:
                raise ValueError(
                    "Configuration comparisons must use the same evaluated case manifest."
                )
            comparisons.append(other)
        chunking = {item["settings"].get("chunk_strategy") for item in comparisons}
        modes = {
            item.get("request_overrides", {}).get("mode") or item["settings"].get("retrieval_mode")
            for item in comparisons
        }
        if not {"fixed", "structure"} <= chunking or not {"dense", "hybrid"} <= modes:
            raise ValueError(
                "Measured comparisons must cover fixed/structure chunking and dense/hybrid retrieval."
            )
        add(
            "configuration_comparisons",
            True,
            "Comparable real-provider reports cover both required ablations.",
            {
                "reports": len(comparisons),
                "chunk_strategies": sorted(chunking),
                "retrieval_modes": sorted(modes),
            },
            "recorded_runs",
        )
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as error:
        add("configuration_comparisons", False, str(error))

    try:
        review = _object(_artifact(root, manifest.get("manual_review_report")))
        if report is None or not evaluation_evidence:
            raise ValueError("Manual review must reference a valid final evaluation artifact.")
        if (
            review.get("reviewer_kind") != "human"
            or not str(review.get("reviewer", "")).strip()
            or review.get("approved") is not True
            or review.get("evaluation_file_sha256") != evaluation_evidence["file_sha256"]
        ):
            raise ValueError(
                "Manual review needs a named human reviewer, approval and the exact evaluation file hash."
            )
        _time(review.get("reviewed_at"))
        case_by_id = {row["case"]["id"]: row["case"] for row in report["rows"]}
        counts: Counter[str] = Counter()
        seen = set()
        for item in review.get("cases", []):
            identity = item.get("case_id")
            case = case_by_id.get(identity)
            if (
                not case
                or identity in seen
                or case.get("split") != "test"
                or item.get("citation_entailment_checked") is not True
                or item.get("outcome")
                not in {"supported", "withheld_correctly", "documented_failure"}
                or not str(item.get("notes", "")).strip()
            ):
                raise ValueError(
                    "Manual review cases need unique actual test IDs, source/entailment checks, outcomes and notes."
                )
            seen.add(identity)
            counts[case["category"]] += 1
        if any(counts[category] < 5 for category in REQUIRED_CATEGORIES):
            raise ValueError(
                "Manual review must cover at least five test answers in each required category."
            )
        add(
            "manual_answer_review",
            True,
            "Named human review with per-case findings is supplied; this audit does not independently observe the review.",
            {
                "reviewer": review["reviewer"],
                "reviewed_at": review["reviewed_at"],
                "reviewed_cases": len(seen),
            },
            "human_attestation",
        )
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as error:
        add(
            "manual_answer_review",
            False,
            str(error),
            required=bool(manifest.get("manual_review_report")),
        )

    live_url = None
    health: dict[str, Any] | None = None
    try:
        live_url = _public_https(manifest.get("live_demo_url"))
        if not check_urls:
            raise ValueError(
                "Live URL supplied but not contacted. Enable URL checks to verify /health and /ready."
            )
        with httpx.Client(timeout=5, follow_redirects=False) as client:
            response = client.get(live_url + "/health")
            ready = client.get(live_url + "/ready")
            response.raise_for_status()
            ready.raise_for_status()
            health = response.json()
            if (
                not isinstance(health, dict)
                or health.get("status") != "ok"
                or ready.json().get("status") != "ready"
            ):
                raise ValueError(
                    "Public health/readiness endpoints did not confirm a working application."
                )
            UUID(health.get("boot_id", ""))
            _time(health.get("started_at"))
        add(
            "public_live_demo",
            True,
            "Public HTTPS health and readiness endpoints responded without redirects.",
            {"url": live_url, "health": health},
        )
    except (ValueError, OSError, httpx.HTTPError, TypeError, AttributeError) as error:
        add(
            "public_live_demo",
            False,
            str(error)
            if isinstance(error, ValueError)
            else f"Public endpoint check failed ({type(error).__name__}).",
        )

    try:
        repository = _public_https(manifest.get("repository_url"))
        parsed = urlparse(repository)
        segments = parsed.path.strip("/").removesuffix(".git").split("/")
        if parsed.hostname != "github.com" or len(segments) != 2 or not all(segments):
            raise ValueError(
                "Supply the GitHub repository URL in https://github.com/account/repository form."
            )
        if not check_urls or not commit:
            raise ValueError(
                "Repository publication is not verified until URL checks can find the local commit on GitHub."
            )
        with httpx.Client(timeout=5, follow_redirects=False) as client:
            response = client.get(
                f"https://api.github.com/repos/{'/'.join(segments)}/commits/{commit}"
            )
            response.raise_for_status()
            if response.json().get("sha") != commit:
                raise ValueError("The current local commit was not found in the public repository.")
        add(
            "published_repository",
            True,
            "The current local commit resolves in the public GitHub repository.",
            {"url": repository, "commit": commit},
        )
    except (ValueError, OSError, httpx.HTTPError, TypeError, AttributeError) as error:
        add(
            "published_repository",
            False,
            str(error)
            if isinstance(error, ValueError)
            else f"Repository publication check failed ({type(error).__name__}).",
        )

    try:
        capture = _object(_artifact(root, manifest.get("deployment_evidence")))
        if _public_https(capture.get("base_url")) != live_url:
            raise ValueError("Restart observations must use the submitted live application URL.")
        before, after = capture.get("health_before", {}), capture.get("health_after", {})
        UUID(before.get("boot_id", ""))
        UUID(after.get("boot_id", ""))
        before_observed = _time(capture.get("observed_before_at"))
        after_observed = _time(capture.get("observed_after_at"))
        if (
            before.get("status") != "ok"
            or after.get("status") != "ok"
            or before["boot_id"] == after["boot_id"]
            or not (
                _time(before.get("started_at"))
                <= before_observed
                < _time(after.get("started_at"))
                <= after_observed
            )
            or after_observed > datetime.now(UTC)
            or not str(capture.get("captured_by", "")).strip()
        ):
            raise ValueError(
                "Restart evidence requires captured, time-ordered, distinct application instances."
            )
        doc_before, doc_after = (
            capture.get("document_before", {}),
            capture.get("document_after", {}),
        )
        fields = ("id", "revision", "checksum")
        if (
            any(doc_before.get(key) != doc_after.get(key) for key in fields)
            or not isinstance(doc_after.get("id"), str)
            or not doc_after["id"]
            or type(doc_after.get("revision")) is not int
            or doc_after["revision"] < 1
            or not isinstance(doc_after.get("checksum"), str)
            or not HEX64.fullmatch(doc_after["checksum"])
        ):
            raise ValueError(
                "Before/after source identity, revision and checksum must match and be valid."
            )
        UUID(doc_after["id"])
        if not check_urls or not health or health["boot_id"] != after["boot_id"]:
            raise ValueError(
                "The current live health response must match the captured after-restart application instance."
            )
        with httpx.Client(timeout=5, follow_redirects=False) as client:
            response = client.get(live_url + "/api/v1/documents/" + doc_after["id"])
            response.raise_for_status()
            current = response.json()
            if (
                any(current.get(key) != doc_after[key] for key in fields)
                or current.get("status") != "ready"
            ):
                raise ValueError(
                    "Current live source does not match the captured persistent source."
                )
        add(
            "restart_persistence",
            True,
            "Captured application-instance transition and unchanged source match current live HTTP observations. Prior captures are retained evidence, not cryptographic proof.",
            {
                "document_id": doc_after["id"],
                "before_boot_id": before["boot_id"],
                "after_boot_id": after["boot_id"],
                "captured_by": capture["captured_by"],
            },
            "captured_transition_and_current_http",
        )
    except (ValueError, OSError, httpx.HTTPError, TypeError, KeyError, AttributeError) as error:
        add(
            "restart_persistence",
            False,
            str(error)
            if isinstance(error, ValueError)
            else f"Restart/source verification failed ({type(error).__name__}).",
        )

    return {
        "status": "pass"
        if all(check["status"] == "pass" for check in checks if check["required"])
        else "incomplete",
        "checked_at": utc_now(),
        "check_urls": check_urls,
        "checks": checks,
        "limitations": [
            "This audit validates supplied evidence and current observations; it does not independently rerun model evaluations or authenticate historical captures/human reviews.",
            "A Store count verifies active records, not complete manifest-ID reconciliation or hosted vector-database performance.",
            "Passing this package audit is not a guarantee of perfect answer quality or a particular assessment score.",
        ],
    }

"""Reproducible development, dataset, evaluation and operations commands."""

import json
import logging
import time
from pathlib import Path
from typing import Annotated, Literal

import typer

from investigation.config import Settings
from investigation.models import InvestigationRequest, Job

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
    help="Build and investigate an attributable document corpus.",
)


def emit(value: object) -> None:
    typer.echo(json.dumps(value, indent=2, ensure_ascii=False, default=str))


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000):
    """Start the API and user interface (one process for local embedded Qdrant)."""
    import uvicorn

    uvicorn.run("investigation.web:create_app", host=host, port=port, factory=True, log_config=None)


@app.command()
def seed(output: Path = Path("data/corpus/seed"), ingest: bool = False):
    """Create the authored incident fixture and independent question manifest."""
    from investigation.datasets import seed_records, write_seed

    emit(write_seed(output))
    if ingest:
        from investigation.runtime import build_runtime

        runtime = build_runtime()
        try:
            emit(runtime.ingestion.ingest_records(seed_records()))
            emit(runtime.store.stats())
        finally:
            runtime.close()


@app.command("prepare-dataset")
def prepare_dataset(
    output: Path = Path("data/corpus/hotpot"),
    records: int = 50000,
    seed: int = 42,
    questions: int = 20,
):
    """Download immutable HotpotQA sources and produce a hashed >=50k passage corpus."""
    from investigation.datasets import prepare_hotpot

    emit(prepare_hotpot(output, minimum_records=records, seed=seed, max_eval_questions=questions))


@app.command("ingest")
def ingest_command(path: Annotated[Path, typer.Argument(exists=True)], batch_size: int = 64):
    """Index a JSONL corpus or an individual PDF/DOCX/TXT/MD document. Safe to replay."""
    from investigation.datasets import file_sha256, read_jsonl
    from investigation.runtime import build_runtime

    runtime = build_runtime()
    job = Job(
        status="running",
        message=f"Indexing {path.name}",
        metadata={
            "source_name": path.name,
            "source_sha256": file_sha256(path),
            "batch_size": batch_size,
        },
    )
    runtime.store.put_job(job)
    began = time.perf_counter()
    try:
        if path.suffix.lower() == ".jsonl":

            def progress(counts):
                job.processed = counts["processed"]
                job.failed = counts["failed"]
                job.metadata["counts"] = counts.copy()
                runtime.store.put_job(job)
                typer.echo(
                    f"processed={job.processed} created={counts['created']} duplicates={counts['duplicates']} failed={job.failed}",
                    err=True,
                )

            counts = runtime.ingestion.ingest_records(
                read_jsonl(path), batch_size, progress=progress
            )
            job.metadata["counts"] = counts
            emit(counts)
        else:
            result = runtime.ingestion.ingest(path.name, path.read_bytes())
            job.processed = 1
            emit(
                {
                    "status": result.status,
                    "document_id": result.document.id,
                    "chunks": result.document.chunk_count,
                }
            )
        job.status = "failed" if job.failed else "complete"
        job.message = f"Finished in {time.perf_counter() - began:.1f} seconds"
        job.metadata["elapsed_seconds"] = time.perf_counter() - began
        runtime.store.put_job(job)
        emit({"job": job.model_dump(), "store": runtime.store.stats()})
        if job.failed:
            raise typer.Exit(1)
    except (Exception, KeyboardInterrupt) as error:
        job.status, job.message = (
            "failed",
            f"Import interrupted: {type(error).__name__}. Replay the same corpus to resume.",
        )
        runtime.store.put_job(job)
        raise
    finally:
        runtime.close()


@app.command()
def ask(
    question: Annotated[str, typer.Argument()],
    mode: Literal["dense", "sparse", "hybrid"] | None = None,
    rerank: bool = True,
):
    """Run the exact same validated investigation pipeline used by the UI."""
    from investigation.runtime import build_runtime

    runtime = build_runtime()
    try:
        answer = runtime.engine.investigate(
            InvestigationRequest(question=question, mode=mode, rerank=rerank)
        )
        emit(answer.model_dump())
    finally:
        runtime.close()


@app.command("evaluate")
def evaluate_command(
    cases: Annotated[Path, typer.Argument(exists=True)],
    output: Path = Path("reports/evaluation/default"),
    name: str = "default",
    mode: Literal["dense", "sparse", "hybrid"] | None = None,
    rerank: bool | None = None,
    limit: int | None = None,
    split: str = "test",
    resume: bool = False,
    max_new_cases: Annotated[int | None, typer.Option(min=1)] = None,
    stop_on_error: bool = False,
    request_interval_seconds: Annotated[float | None, typer.Option(min=0, max=60)] = None,
):
    """Record per-case predictions, citations, traces and quantitative metrics."""
    from investigation.evaluation import evaluate, load_cases
    from investigation.runtime import build_runtime

    settings = Settings()
    if request_interval_seconds is not None:
        settings.llm_min_request_interval_seconds = request_interval_seconds
    runtime = build_runtime(settings)
    try:
        manifest = load_cases(cases)
        if split != "all":
            if split not in ("test", "tuning", "security", "test-security"):
                raise typer.BadParameter(
                    "split must be test, tuning, security, test-security or all"
                )
            splits = {"test", "security"} if split == "test-security" else {split}
            manifest = [case for case in manifest if case.split in splits]
        if limit is not None:
            manifest = manifest[:limit]
        report = evaluate(
            runtime.engine,
            manifest,
            output,
            name,
            {"mode": mode, "rerank": rerank},
            resume=resume,
            max_new_cases=max_new_cases,
            stop_on_error=stop_on_error,
        )
        emit(
            {
                "configuration": name,
                "status": report["status"],
                "case_count": report["case_count"],
                "planned_case_count": report["planned_case_count"],
                "aggregate": report["aggregate"],
                "output": str(output),
            }
        )
        if report["status"] != "complete":
            raise typer.Exit(2)
    finally:
        runtime.close()


@app.command()
def compare(
    paths: Annotated[list[Path], typer.Argument()], output: Path = Path("reports/comparison.md")
):
    """Compare saved reports only when their evaluation manifests match."""
    from investigation.evaluation import compare_reports

    typer.echo(compare_reports(paths, output))


@app.command()
def benchmark(
    cases: Annotated[Path, typer.Argument(exists=True)],
    output: Path = Path("reports/performance"),
    questions: int = 10,
    repeats: int = 1,
    concurrency: int = 1,
    corpus: Path | None = None,
):
    """Measure real end-to-end latency, memory, errors and throughput."""
    from investigation.benchmark import run_benchmark
    from investigation.evaluation import load_cases
    from investigation.runtime import build_runtime

    runtime = build_runtime()
    try:
        if corpus:
            from investigation.verification import reconcile_corpus

            verified = reconcile_corpus(runtime.store, corpus)
            output.mkdir(parents=True, exist_ok=True)
            (output / "corpus-reconciliation.json").write_text(
                json.dumps(verified, indent=2) + "\n", encoding="utf-8"
            )
            if verified["status"] != "pass":
                raise ValueError("Benchmark corpus failed ID/content/source reconciliation")
        report = run_benchmark(
            runtime.engine,
            [c.question for c in load_cases(cases)[:questions]],
            output,
            repeats,
            concurrency,
        )
        emit({k: v for k, v in report.items() if k != "rows"})
    finally:
        runtime.close()


@app.command()
def status():
    """Inspect persisted corpus counts and safe runtime configuration."""
    from investigation.runtime import build_runtime

    runtime = build_runtime()
    try:
        emit(
            {
                **runtime.store.stats(),
                "provider": runtime.settings.llm_provider,
                "model": runtime.settings.llm_model,
                "embedding": runtime.embedder.fingerprint,
                "chunking": runtime.settings.chunk_strategy,
                "reranking": runtime.settings.reranker_enabled,
            }
        )
    finally:
        runtime.close()


@app.command()
def experiments(
    corpus: Annotated[Path, typer.Argument(exists=True)],
    cases: Annotated[Path, typer.Argument(exists=True)],
    output: Path = Path("reports/experiments"),
    records: int = 1000,
    alternative_model: bool = True,
    resume: bool = False,
    max_new_cases: Annotated[int | None, typer.Option(min=1)] = None,
    stop_on_error: bool = False,
    request_interval_seconds: Annotated[float | None, typer.Option(min=0, max=60)] = None,
):
    """Run isolated chunking, retrieval, reranking and semantic model comparisons."""
    from investigation.experiments import run_experiments

    settings = Settings()
    if request_interval_seconds is not None:
        settings.llm_min_request_interval_seconds = request_interval_seconds
    result = run_experiments(
        settings,
        corpus,
        cases,
        output,
        minimum_records=records,
        include_alternative_model=alternative_model,
        resume=resume,
        max_new_cases=max_new_cases,
        stop_on_error=stop_on_error,
    )
    emit(result)
    if result["status"] != "complete":
        raise typer.Exit(2)


@app.command("judge")
def judge_command(
    report: Annotated[Path, typer.Argument(exists=True)],
    output: Path = Path("reports/semantic-review"),
    limit: int | None = None,
):
    """Optionally review saved predictions with a disclosed semantic LLM rubric."""
    from investigation.judge import judge_report

    result = judge_report(Settings(), report, output, limit)
    emit({k: v for k, v in result.items() if k != "rows"})


@app.command("audit")
def audit_command(
    manifest: Path = Path("submission.example.json"),
    with_store: bool = False,
    check_urls: bool = False,
    output: Path = Path("reports/submission-audit.json"),
):
    """Check actual submission evidence; incomplete gates produce a nonzero exit."""
    from investigation.storage import Store
    from investigation.submission import audit_submission

    store = None
    try:
        if with_store:
            settings = Settings()
            store = Store(settings, settings.embedding_dimension)
        result = audit_submission(Path.cwd(), manifest, store, check_urls)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        emit(result)
        if result["status"] != "pass":
            raise typer.Exit(1)
    finally:
        if store:
            store.close()


@app.command("reconcile")
def reconcile_command(
    corpus: Annotated[Path, typer.Argument(exists=True)],
    output: Path = Path("reports/corpus-reconciliation.json"),
):
    """Verify every source ID, content checksum and source URL against Qdrant."""
    from investigation.storage import Store
    from investigation.verification import reconcile_corpus

    settings = Settings()
    store = Store(settings, settings.embedding_dimension)
    try:
        result = reconcile_corpus(store, corpus)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        emit(result)
        if result["status"] != "pass":
            raise typer.Exit(1)
    finally:
        store.close()


@app.command("download-models")
def download_models(reranker: bool = True):
    """Pre-download CPU models; no user documents or credentials are uploaded."""
    from investigation.embeddings import make_embedder
    from investigation.models import Chunk, SearchHit
    from investigation.retrieval import Reranker

    settings = Settings()
    embedder = make_embedder(settings)
    try:
        vector = embedder.embed(["Verify semantic retrieval model readiness."])[0]
        emit({"embedding": embedder.fingerprint, "dimension": len(vector)})
        if reranker:
            hit = SearchHit(
                chunk=Chunk(
                    id="download-check",
                    document_id="check",
                    revision=1,
                    title="Model check",
                    text="Semantic retrieval locates evidence.",
                    checksum="check",
                ),
                score=1,
            )
            Reranker(settings).rerank("How is evidence retrieved?", [hit])
            emit({"reranker": settings.reranker_model, "status": "ready"})
    finally:
        close = getattr(embedder, "close", None)
        if close:
            close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app()

import pytest

from investigation.config import Settings
from investigation.embeddings import HashEmbedder
from investigation.engine import Engine, evidence_payload, numeric_conflicts
from investigation.errors import ProviderError
from investigation.ingestion import Ingestor
from investigation.llm import (
    AnswerDraft,
    DraftClaim,
    DraftConflict,
    EvidenceReference,
    ToolCall,
    ToolProposal,
    Verification,
)
from investigation.models import Chunk, InvestigationRequest, SearchFilters, SearchHit
from investigation.storage import Store


@pytest.fixture
def components(tmp_path):
    settings = Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path,
        embedding_backend="hash",
        embedding_dimension=64,
        llm_provider="ollama",
        reranker_enabled=False,
        chunk_tokens=64,
        chunk_overlap=8,
    )
    embedder = HashEmbedder(64)
    store = Store(settings, 64)
    ingestion = Ingestor(store, embedder, settings)
    document = ingestion.ingest(
        "atlas.txt",
        b"Atlas gateway timeout was 250 milliseconds. Orion owns the Atlas gateway.",
        metadata={"dataset": "visible", "project": "Atlas"},
    ).document
    yield settings, embedder, store, ingestion, document
    store.close()


def test_engine_shares_provider_pacing_between_investigation_clients(components):
    settings, embedder, store, _, _ = components
    settings.llm_min_request_interval_seconds = 12
    engine = Engine(settings, store, embedder)
    first, second = engine.llm_factory(), engine.llm_factory()
    try:
        assert first.pacer is second.pacer
        assert first.pacer.interval_seconds == 12
    finally:
        first.close()
        second.close()
        engine.close()


class FixtureLLM:
    """Only a test double; never counted as a real provider evaluation."""

    usage = {"calls": 3, "input_tokens": 100, "output_tokens": 25}

    def __init__(self, invalid_quote=False, reject=False):
        self.invalid_quote = invalid_quote
        self.reject = reject
        self.closed = False

    def propose_tools(self, question):
        return ToolProposal(
            calls=[ToolCall(name="search_documents", arguments={"query": "Atlas gateway timeout"})]
        )

    def follow_up(self, *args):
        return ToolProposal(calls=[])

    def synthesize(self, question, passages, proposal, tool_results):
        return AnswerDraft(
            status="answered",
            claims=[
                DraftClaim(
                    text="The Atlas gateway timeout was 250 milliseconds.",
                    evidence=[
                        EvidenceReference(
                            passage_id=passages[0]["passage_id"],
                            quote="900 invented milliseconds"
                            if self.invalid_quote
                            else "250 milliseconds",
                        )
                    ],
                )
            ],
        )

    def verify(self, *args):
        return Verification(
            unsupported_claim_indices=[0] if self.reject else [],
            answer_addresses_question=True,
            unresolved_conflict=False,
            reason="Fixture verdict",
        )

    def close(self):
        self.closed = True


@pytest.mark.parametrize("confirmed", [False, True])
def test_conflict_requires_independent_semantic_confirmation_not_only_two_quotes(
    components, confirmed
):
    settings, embedder, store, ingestion, _ = components
    entity = "Atlas" if confirmed else "Birch"
    ingestion.ingest("second.txt", f"{entity} gateway timeout was 700 milliseconds.".encode())
    llm = FixtureLLM()
    verifications = []

    def synthesize(question, passages, proposal, tool_results):
        first = next(p for p in passages if "250 milliseconds" in p["text"])
        second = next(p for p in passages if "700 milliseconds" in p["text"])
        return AnswerDraft(
            status="conflicting_evidence",
            conflicts=[
                DraftConflict(
                    description="The sources disagree about the Atlas gateway timeout.",
                    evidence=[
                        EvidenceReference(passage_id=first["passage_id"], quote="250 milliseconds"),
                        EvidenceReference(
                            passage_id=second["passage_id"], quote="700 milliseconds"
                        ),
                    ],
                )
            ],
        )

    def verify(*args):
        verifications.append(1)
        return Verification(
            unsupported_claim_indices=[],
            answer_addresses_question=True,
            unresolved_conflict=confirmed,
            reason="Same entity conflict"
            if confirmed
            else "Different entities do not contradict each other",
        )

    llm.synthesize, llm.verify = synthesize, verify
    answer = Engine(settings, store, embedder, llm_factory=lambda: llm).investigate(
        InvestigationRequest(question="What was the Atlas gateway timeout?")
    )
    assert verifications == [1]
    assert answer.status == ("conflicting_evidence" if confirmed else "insufficient_evidence")
    assert bool(answer.conflicts) is confirmed


def test_llm_claim_citations_resolve_to_stored_passage_with_exact_quote(components):
    settings, embedder, store, _, doc = components
    llm = FixtureLLM()
    engine = Engine(settings, store, embedder, llm_factory=lambda: llm)
    result = engine.investigate(
        InvestigationRequest(question="What was the Atlas gateway timeout?")
    )
    assert result.status == "answered" and result.claims
    citation = result.citations[0]
    assert citation.document_id == doc.id and citation.quote == "250 milliseconds"
    assert citation.quote in store.get_chunks([citation.passage_id])[0].text
    assert result.claims[0].citation_ids == [citation.id]
    assert llm.closed


@pytest.mark.parametrize("invalid_quote,reject", [(True, False), (False, True)])
def test_invalid_citation_or_verifier_rejection_withholds_model_answer(
    components, invalid_quote, reject
):
    settings, embedder, store, _, _ = components
    llm = FixtureLLM(invalid_quote=invalid_quote, reject=reject)
    result = Engine(settings, store, embedder, llm_factory=lambda: llm).investigate(
        InvestigationRequest(question="What was the Atlas gateway timeout?")
    )
    assert result.status == "insufficient_evidence"
    assert result.claims == []
    assert "900 invented" not in result.answer
    assert result.warnings and llm.closed


def test_unknown_tools_and_extra_filters_cannot_escape_user_scope(components):
    settings, embedder, store, ingest, _ = components
    secret = ingest.ingest(
        "restricted.txt",
        b"Restricted Atlas gateway secret project information.",
        metadata={"dataset": "restricted"},
    ).document
    engine = Engine(settings, store, embedder)
    before = store.stats()
    request = InvestigationRequest(
        question="What is the Atlas gateway timeout?", filters=SearchFilters(dataset="visible")
    )
    known, trace = {}, []
    calls = [
        ToolCall(name="delete_document", arguments={"document_id": secret.id}),
        ToolCall(
            name="search_documents",
            arguments={"query": "Atlas gateway", "filters": {"dataset": "restricted"}},
        ),
        ToolCall(name="inspect_document", arguments={"document_id": secret.id}),
        ToolCall(name="fetch_passages", arguments={"passage_ids": ["unknown-passage"]}),
    ]
    results, _ = engine._execute_tools(calls, request, known, trace)
    assert "error" in results[0]["result"]
    assert results[2]["result"]["document"] is None
    assert results[3]["result"]["passages"] == []
    assert all(hit.chunk.document_id != secret.id for hit in known.values())
    assert before == store.stats()


def test_tool_call_budget_and_provider_failure_release_investigation_slot(components):
    settings, embedder, store, _, _ = components
    llm = FixtureLLM()
    llm.propose_tools = lambda question: ToolProposal(
        calls=[ToolCall(name="search_documents", arguments={"query": "Atlas"})] * 7
    )
    engine = Engine(settings, store, embedder, llm_factory=lambda: llm)
    request = InvestigationRequest(question="What was the Atlas gateway timeout?")
    for _ in range(settings.max_concurrent_investigations + 1):
        with pytest.raises(ProviderError, match="budget"):
            engine.investigate(request)
    assert llm.closed


@pytest.mark.parametrize(
    "arguments", [{"query": {"not": "a string"}}, {"query": "Atlas", "limit": 999}]
)
def test_malformed_model_tool_arguments_are_rejected_without_breaking_answer_contract(
    components, arguments
):
    settings, embedder, store, _, _ = components
    llm = FixtureLLM()
    llm.propose_tools = lambda question: ToolProposal(
        calls=[ToolCall(name="search_documents", arguments=arguments)]
    )
    result = Engine(settings, store, embedder, llm_factory=lambda: llm).investigate(
        InvestigationRequest(question="What was the Atlas gateway timeout?")
    )
    assert result.status == "insufficient_evidence"
    assert all(isinstance(query, str) for query in result.plan.subquestions)
    assert llm.closed


def test_answer_cache_is_invalidated_when_evidence_is_deleted(components):
    settings, embedder, store, _, doc = components
    preview = settings.model_copy(update={"llm_provider": "extractive"})
    engine = Engine(preview, store, embedder)
    request = InvestigationRequest(question="What was the Atlas gateway timeout?")
    first = engine.investigate(request)
    assert first.status == "answered" and not first.cached
    assert engine.investigate(request).cached
    store.delete_document(doc.id)
    after_delete = engine.investigate(request)
    assert not after_delete.cached
    assert after_delete.status == "insufficient_evidence"
    assert after_delete.citations == []
    assert after_delete.corpus_revision != first.corpus_revision


def test_source_deleted_during_generation_cannot_publish_stale_citation(components):
    settings, embedder, store, _, document = components
    llm = FixtureLLM()
    original = llm.synthesize

    def deleting_synthesis(*args):
        draft = original(*args)
        store.delete_document(document.id)
        return draft

    llm.synthesize = deleting_synthesis
    result = Engine(settings, store, embedder, llm_factory=lambda: llm).investigate(
        InvestigationRequest(question="What was the Atlas gateway timeout?")
    )
    assert result.status == "insufficient_evidence"
    assert result.citations == [] and result.claims == []
    assert any("stale" in warning for warning in result.warnings)


def test_numeric_conflicts_require_matching_subject_entity_and_time():
    def audit(identity, count, date="2026-03-03", project="Atlas"):
        return SearchHit(
            chunk=Chunk(
                id=identity,
                document_id=identity,
                revision=1,
                title="Audit",
                text=f"Audit export for {project} on {date}. The number of failed payment requests was {count}.",
                checksum=identity,
                metadata={"project": project},
            ),
            score=1,
        )

    assert len(numeric_conflicts([audit("a", 101), audit("b", 301)])) == 1
    assert numeric_conflicts([audit("a", 101), audit("b", 101)]) == []
    assert numeric_conflicts([audit("a", 101), audit("b", 301, date="2026-04-03")]) == []
    assert numeric_conflicts([audit("a", 101), audit("b", 301, project="Birch")]) == []


def test_context_budget_never_cuts_quoted_source_text():
    hit = SearchHit(
        chunk=Chunk(
            id="p",
            document_id="d",
            revision=1,
            title="Evidence",
            text="A complete evidence sentence.",
            checksum="x",
        ),
        score=1,
    )
    assert evidence_payload([hit], max_chars=5) == []
    assert evidence_payload([hit], max_chars=100)[0]["text"] == hit.chunk.text

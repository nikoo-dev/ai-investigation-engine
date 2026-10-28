"""Bounded plan -> tool retrieval -> evidence verification -> cited synthesis."""

import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Iterator
from typing import Any, Literal, cast

from pydantic import BaseModel, Field, ValidationError

from investigation.config import Settings
from investigation.embeddings import Embedder, fingerprint_json, lexical_tokens
from investigation.errors import BusyError, ProviderError
from investigation.llm import AnswerDraft, LLMClient, ToolCall, ToolProposal
from investigation.models import (
    Citation,
    Claim,
    Conflict,
    InvestigationAnswer,
    InvestigationPlan,
    InvestigationRequest,
    SearchHit,
    TraceStep,
)
from investigation.retrieval import Retriever, diversify, reciprocal_rank_fusion

log = logging.getLogger(__name__)
INJECTION = re.compile(
    r"ignore.{0,30}instructions|system\s+prompt|reveal.{0,30}secret|print.{0,30}api.?key", re.I
)


class SearchArguments(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=8, ge=1, le=12)


class FetchArguments(BaseModel):
    passage_ids: list[str] = Field(min_length=1, max_length=12)


class InspectArguments(BaseModel):
    document_id: str


def basic_plan(question: str) -> InvestigationPlan:
    comparison = bool(
        re.search(r"\b(compare|more|fewer|earlier|later|both|difference|versus)\b", question, re.I)
    )
    multi = bool(
        re.search(
            r"\b(cause|caused|which.*and|what.*and|confirm|owned|wife|father|mother)\b",
            question,
            re.I,
        )
    )
    return InvestigationPlan(
        kind="comparison" if comparison else "multi_hop" if multi else "direct",
        subquestions=[question],
        rationale="Bounded retrieval followed by evidence validation.",
    )


def evidence_payload(hits: list[SearchHit], max_chars: int) -> list[dict]:
    result = []
    used = 0
    for hit in hits:
        # Never clip inside a quote: downstream citations must match exactly.
        if used + len(hit.chunk.text) > max_chars:
            continue
        used += len(hit.chunk.text)
        result.append(
            {
                "passage_id": hit.chunk.id,
                "document_id": hit.chunk.document_id,
                "title": hit.chunk.title,
                "text": hit.chunk.text,
                "revision": hit.chunk.revision,
                "location": hit.chunk.location.model_dump(),
            }
        )
    return result


def numeric_conflicts(hits: list[SearchHit]) -> list[tuple[str, list[tuple[SearchHit, str]]]]:
    """Conservative same-subject/time numeric disagreement detector.

    A shared dataset entity/project and explicit date are required. We never infer
    contradictions merely from two different numbers or from different revisions.
    Semantic/negation contradictions are additionally checked by the LLM verifier.
    """
    grouped: dict[tuple, dict[str, tuple[SearchHit, str]]] = {}
    for hit in hits:
        text = hit.chunk.text
        entity = hit.chunk.metadata.get("project") or hit.chunk.metadata.get("entity")
        date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
        if not entity or not date:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            match = re.fullmatch(
                r"(.{8,180}?)\s+(?:was|is|were|are)\s+(\d+(?:\.\d+)?)\s*([^.!?]*?)[.!?]?",
                sentence.strip(),
                re.I,
            )
            if not match:
                continue
            key = (
                str(entity).casefold(),
                date.group(),
                match[1].casefold().strip(),
                match[3].casefold().strip(),
            )
            grouped.setdefault(key, {})[match[2]] = (hit, sentence.strip())
    return [
        (f"Sources disagree about {key[2]} for {key[0]} on {key[1]}.", list(values.values()))
        for key, values in grouped.items()
        if len(values) > 1
    ]


class Engine:
    def __init__(self, settings: Settings, store, embedder: Embedder, llm_factory=None):
        self.settings = settings
        self.store = store
        self.embedder = embedder
        self.retriever = Retriever(store, embedder, settings)
        self._slots = threading.BoundedSemaphore(settings.max_concurrent_investigations)
        self._cache: OrderedDict = OrderedDict()
        self._cache_lock = threading.Lock()
        self.llm_factory = llm_factory or (lambda: LLMClient(settings))

    def close(self) -> None:
        self.retriever.reranker.close()
        with self._cache_lock:
            self._cache.clear()

    def investigate(self, request: InvestigationRequest) -> InvestigationAnswer:
        answer = None
        for event in self.stream(request):
            if event["event"] == "answer":
                answer = InvestigationAnswer.model_validate(event["data"])
        if answer is None:
            raise ProviderError("Investigation ended without a validated answer.")
        return answer

    def stream(self, request: InvestigationRequest) -> Iterator[dict]:
        if not self._slots.acquire(blocking=False):
            raise BusyError("All investigation slots are busy. Please retry shortly.")
        try:
            yield from self._run(request)
        finally:
            self._slots.release()

    def _execute_tools(
        self,
        calls: list[ToolCall],
        request: InvestigationRequest,
        known_hits: dict[str, SearchHit],
        trace: list[TraceStep],
    ) -> tuple[list[dict], list[list[SearchHit]]]:
        results, rankings = [], []
        for index, call in enumerate(calls):
            started = time.perf_counter()
            result: dict[str, Any]
            try:
                if call.name == "search_documents":
                    args = SearchArguments.model_validate(call.arguments)
                    hits = self.retriever.search(
                        args.query,
                        request.filters,
                        args.limit,
                        request.mode,
                        request.rerank,
                        use_cache=request.use_cache,
                    )
                    for hit in hits:
                        hit.subquestions = [index]
                        known_hits[hit.chunk.id] = hit
                    rankings.append(hits)
                    result = {
                        "passages": evidence_payload(hits, self.settings.max_context_chars // 2)
                    }
                elif call.name == "fetch_passages":
                    fetch_args = FetchArguments.model_validate(call.arguments)
                    # Tools can only expand evidence already discovered under user filters.
                    ids = [key for key in fetch_args.passage_ids if key in known_hits]
                    result = {
                        "passages": evidence_payload(
                            [known_hits[k] for k in ids], self.settings.max_context_chars // 2
                        )
                    }
                elif call.name == "inspect_document":
                    inspect_args = InspectArguments.model_validate(call.arguments)
                    allowed = {h.chunk.document_id for h in known_hits.values()}
                    document = (
                        self.store.get_document(inspect_args.document_id)
                        if inspect_args.document_id in allowed
                        else None
                    )
                    result = {
                        "document": {
                            "id": document.id,
                            "title": document.title,
                            "revision": document.revision,
                            "text": document.text[:6000],
                        }
                        if document
                        else None
                    }
                else:
                    result = {
                        "error": "Unknown tool. Only corpus search, passage fetch and document inspect are allowed."
                    }
            except ValidationError:
                result = {"error": "Tool arguments failed schema validation."}
            results.append({"name": call.name, "id": call.id, "result": result})
            trace.append(
                TraceStep(
                    stage="tool",
                    detail=f"Executed {call.name}",
                    duration_ms=(time.perf_counter() - started) * 1000,
                    metadata={
                        "tool": call.name,
                        "arguments": call.arguments,
                        "passage_count": len(result.get("passages", [])),
                    },
                )
            )
        return results, rankings

    def _run(self, request: InvestigationRequest) -> Iterator[dict]:
        started = time.perf_counter()
        revision = self.store.corpus_revision()
        key = fingerprint_json(
            [
                request.model_dump(exclude={"use_cache"}),
                revision,
                self.settings.llm_provider,
                self.settings.llm_model,
                self.embedder.fingerprint,
                self.settings.reranker_enabled,
            ]
        )
        with self._cache_lock:
            cached = self._cache.get(key)
            if (
                request.use_cache
                and cached
                and time.monotonic() - cached[0] < self.settings.cache_ttl_seconds
            ):
                answer = cached[1].model_copy(deep=True)
                answer.cached = True
                answer.elapsed_ms = (time.perf_counter() - started) * 1000
                yield {"event": "answer", "data": answer.model_dump(mode="json")}
                return
        trace: list[TraceStep] = []
        plan = basic_plan(request.question)
        warnings: list[str] = []
        yield {
            "event": "stage",
            "data": {
                "stage": "planning",
                "message": "Identifying the evidence needed to answer your question.",
            },
        }
        llm = None
        try:
            planning_started = time.perf_counter()
            if self.settings.llm_provider == "extractive":
                proposal = ToolProposal(
                    calls=[
                        ToolCall(
                            name="search_documents",
                            arguments={
                                "query": request.question,
                                "limit": self.settings.evidence_limit,
                            },
                        )
                    ]
                )
                warnings.append(
                    "Extractive evidence preview: no LLM was used. These are source excerpts, not a synthesized or independently verified answer."
                )
            else:
                llm = self.llm_factory()
                proposal = llm.propose_tools(request.question)
            if len(proposal.calls) > self.settings.max_tool_calls:
                raise ProviderError("The investigation exceeded its tool-call budget.")
            plan.subquestions = [
                c.arguments["query"]
                for c in proposal.calls
                if c.name == "search_documents"
                and isinstance(c.arguments.get("query"), str)
                and 2 <= len(c.arguments["query"]) <= 2000
            ][: self.settings.max_subquestions] or [request.question]
            if len(plan.subquestions) > 1 and plan.kind == "direct":
                plan.kind = "multi_hop"
            trace.append(
                TraceStep(
                    stage="planning",
                    detail="Planned focused evidence searches",
                    duration_ms=(time.perf_counter() - planning_started) * 1000,
                    metadata=plan.model_dump(),
                )
            )
            yield {
                "event": "stage",
                "data": {
                    "stage": "retrieval",
                    "message": "Searching semantic and keyword indexes.",
                    "plan": plan.model_dump(),
                },
            }
            known: dict[str, SearchHit] = {}
            tool_results, rankings = self._execute_tools(proposal.calls, request, known, trace)
            if llm and plan.kind != "direct" and len(proposal.calls) < self.settings.max_tool_calls:
                yield {
                    "event": "stage",
                    "data": {
                        "stage": "follow_up",
                        "message": "Checking for a missing link between the retrieved facts.",
                    },
                }
                follow_started = time.perf_counter()
                follow_up = llm.follow_up(request.question, proposal, tool_results)
                trace.append(
                    TraceStep(
                        stage="follow_up",
                        detail="Checked evidence for missing reasoning links",
                        duration_ms=(time.perf_counter() - follow_started) * 1000,
                        metadata={"additional_tool_calls": len(follow_up.calls)},
                    )
                )
                if len(proposal.calls) + len(follow_up.calls) > self.settings.max_tool_calls:
                    raise ProviderError("The investigation exceeded its tool-call budget.")
                if follow_up.calls:
                    extra_results, extra_rankings = self._execute_tools(
                        follow_up.calls, request, known, trace
                    )
                    rankings.extend(extra_rankings)
                    proposal, tool_results = follow_up, extra_results
            hits = diversify(reciprocal_rank_fusion(rankings), self.settings.evidence_limit)
            payload = evidence_payload(hits, self.settings.max_context_chars)
            included = {p["passage_id"] for p in payload}
            hits = [h for h in hits if h.chunk.id in included]
            if any(INJECTION.search(h.chunk.text) for h in hits):
                warnings.append(
                    "Some retrieved source text contains instruction-like content; it is treated only as untrusted evidence."
                )
            yield {
                "event": "stage",
                "data": {
                    "stage": "verification",
                    "message": f"Checking {len(hits)} passages and their source locations.",
                },
            }
            if llm and hits:
                synthesis_started = time.perf_counter()
                draft = llm.synthesize(request.question, payload, proposal, tool_results)
                trace.append(
                    TraceStep(
                        stage="synthesis",
                        detail="Generated a structured evidence-bound draft",
                        duration_ms=(time.perf_counter() - synthesis_started) * 1000,
                    )
                )
                citation_started = time.perf_counter()
                claims, citations, conflicts, invalid = self._validate_draft(draft, hits)
                trace.append(
                    TraceStep(
                        stage="citations",
                        detail="Resolved source identifiers and exact quotations",
                        duration_ms=(time.perf_counter() - citation_started) * 1000,
                        metadata={"invalid": invalid, "citations": len(citations)},
                    )
                )
                status = draft.status
                if invalid:
                    status = "insufficient_evidence"
                    claims, conflicts = [], []
                    warnings.append(
                        "One or more model citations could not be verified; the answer was withheld."
                    )
                elif (status == "answered" and claims) or (
                    status == "conflicting_evidence" and conflicts
                ):
                    verification_started = time.perf_counter()
                    verification = llm.verify(request.question, draft, payload)
                    trace.append(
                        TraceStep(
                            stage="verification",
                            detail=verification.reason,
                            duration_ms=(time.perf_counter() - verification_started) * 1000,
                            metadata=verification.model_dump(),
                        )
                    )
                    if (
                        verification.unsupported_claim_indices
                        or not verification.answer_addresses_question
                    ):
                        status, claims, conflicts = "insufficient_evidence", [], []
                        warnings.append(
                            "Independent evidence verification rejected the proposed answer."
                        )
                    elif status == "conflicting_evidence" and not verification.unresolved_conflict:
                        status, claims, conflicts = "insufficient_evidence", [], []
                        warnings.append(
                            "The independent verifier did not confirm a relevant source conflict."
                        )
                    elif status == "answered" and verification.unresolved_conflict:
                        status = "conflicting_evidence" if conflicts else "insufficient_evidence"
                if status == "answered" and not claims:
                    status = "insufficient_evidence"
                if status == "conflicting_evidence" and not conflicts:
                    status = "insufficient_evidence"
                answer_text = self._render(status, claims, conflicts, draft.missing_evidence)
            elif llm:
                status, claims, citations, conflicts = "insufficient_evidence", [], [], []
                answer_text = (
                    "I could not find evidence in the indexed documents to answer this question."
                )
            else:
                status, claims, citations, conflicts, answer_text = self._extractive(
                    request.question, hits
                )
            if self.store.corpus_revision() != revision:
                # Avoid publishing references to evidence replaced/deleted mid-investigation.
                current = self.store.get_chunks([c.passage_id for c in citations])
                if len(current) != len({c.passage_id for c in citations}):
                    status, claims, citations, conflicts = "insufficient_evidence", [], [], []
                    answer_text = (
                        "The source documents changed during this investigation. Please ask again."
                    )
                    warnings.append(
                        "Corpus changed during investigation; stale evidence was withheld."
                    )
            answer = InvestigationAnswer(
                question=request.question,
                status=cast(
                    Literal["answered", "insufficient_evidence", "conflicting_evidence", "error"],
                    status,
                ),
                answer=answer_text,
                claims=claims,
                citations=citations,
                conflicts=conflicts,
                plan=plan,
                trace=trace,
                retrieved_passage_ids=[h.chunk.id for h in hits],
                retrieved_document_ids=list(dict.fromkeys(h.chunk.document_id for h in hits)),
                model=self.settings.llm_model if llm else "source-excerpts",
                provider=self.settings.llm_provider,
                corpus_revision=revision,
                elapsed_ms=(time.perf_counter() - started) * 1000,
                usage=dict(llm.usage) if llm else {},
                warnings=warnings,
            )
            with self._cache_lock:
                self._cache[key] = (time.monotonic(), answer)
                while len(self._cache) > 128:
                    self._cache.popitem(last=False)
            log.info(
                "investigation_complete",
                extra={
                    "investigation_id": answer.id,
                    "status": status,
                    "elapsed_ms": answer.elapsed_ms,
                    "provider": answer.provider,
                },
            )
            yield {"event": "answer", "data": answer.model_dump(mode="json")}
        finally:
            if llm:
                llm.close()

    def _citation(self, hit: SearchHit, quote: str, number: int) -> Citation:
        doc = self.store.get_document(hit.chunk.document_id)
        return Citation(
            id=f"C{number}",
            passage_id=hit.chunk.id,
            document_id=hit.chunk.document_id,
            revision=hit.chunk.revision,
            title=hit.chunk.title,
            quote=quote,
            location=hit.chunk.location,
            source_uri=doc.source_uri if doc else None,
        )

    def _validate_draft(self, draft: AnswerDraft, hits: list[SearchHit]):
        lookup = {h.chunk.id: h for h in hits}
        citations: list[Citation] = []
        identity: dict[tuple[str, str], str] = {}
        invalid = False

        def references(items):
            nonlocal invalid
            ids = []
            for reference in items:
                hit = lookup.get(reference.passage_id)
                if not hit or reference.quote not in hit.chunk.text:
                    invalid = True
                    continue
                key = (reference.passage_id, reference.quote)
                if key not in identity:
                    cite = self._citation(hit, reference.quote, len(citations) + 1)
                    citations.append(cite)
                    identity[key] = cite.id
                ids.append(identity[key])
            return list(dict.fromkeys(ids))

        claims = [Claim(text=c.text, citation_ids=references(c.evidence)) for c in draft.claims]
        conflicts = []
        for item in draft.conflicts:
            ids = references(item.evidence)
            if len({c.document_id for c in citations if c.id in ids}) < 2:
                invalid = True
            conflicts.append(Conflict(description=item.description, citation_ids=ids))
        return claims, citations, conflicts, invalid

    @staticmethod
    def _render(status, claims, conflicts, missing=""):
        if status == "insufficient_evidence":
            return "The available sources do not establish a reliable answer." + (
                f" Missing evidence: {missing}" if missing else ""
            )
        if status == "conflicting_evidence":
            return "The sources contain unresolved conflicting evidence.\n\n" + "\n".join(
                c.description + " " + " ".join(f"[{x}]" for x in c.citation_ids) for c in conflicts
            )
        return "\n\n".join(
            c.text + " " + " ".join(f"[{x}]" for x in c.citation_ids) for c in claims
        )

    def _extractive(self, question: str, hits: list[SearchHit]):
        query_tokens = set(lexical_tokens(question))
        eligible = [
            h
            for h in hits
            if (h.dense_score or 0) >= self.settings.min_dense_score
            or len(query_tokens & set(lexical_tokens(h.chunk.text))) / max(1, len(query_tokens))
            >= 0.35
        ]
        citations: list[Citation] = []
        conflicts = []
        for description, alternatives in numeric_conflicts(eligible):
            ids = []
            for hit, sentence in alternatives:
                cite = self._citation(hit, sentence, len(citations) + 1)
                citations.append(cite)
                ids.append(cite.id)
            conflicts.append(Conflict(description=description, citation_ids=ids))
        if conflicts:
            return (
                "conflicting_evidence",
                [],
                citations,
                conflicts,
                self._render("conflicting_evidence", [], conflicts),
            )
        scored = []
        for hit in eligible:
            for sentence in re.split(r"(?<=[.!?])\s+", hit.chunk.text):
                tokens = set(lexical_tokens(sentence))
                if not INJECTION.search(sentence) and len(sentence) > 15:
                    scored.append(
                        (len(query_tokens & tokens) / max(1, len(query_tokens)), hit, sentence)
                    )
        scored.sort(key=lambda item: (-item[0], -item[1].score, item[1].chunk.id))
        claims = []
        seen = set()
        for overlap, hit, sentence in scored:
            if overlap < 0.12 or sentence in seen:
                continue
            seen.add(sentence)
            cite = self._citation(hit, sentence, len(citations) + 1)
            citations.append(cite)
            claims.append(Claim(text=sentence, citation_ids=[cite.id]))
            if len(claims) >= 5:
                break
        if not claims:
            return (
                "insufficient_evidence",
                [],
                [],
                [],
                "I could not find sufficiently relevant evidence in the indexed documents.",
            )
        # This status only describes available excerpts; the UI prominently labels the mode.
        return (
            "answered",
            claims,
            citations,
            [],
            "Source excerpts (no LLM synthesis):\n\n" + self._render("answered", claims, []),
        )

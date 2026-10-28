import json

import httpx
import pytest

from investigation.config import Settings
from investigation.errors import ProviderError
from investigation.llm import (
    AnswerDraft,
    LLMClient,
    RequestPacer,
    ToolCall,
    ToolProposal,
    Verification,
    gemini_output_schema,
)


def settings(**overrides):
    return Settings(
        _env_file=None,
        environment="test",
        llm_provider="gemini",
        gemini_api_key="test-secret-never-in-url",
        llm_model="fixture-model",
        llm_max_retries=0,
        **overrides,
    )


def test_shared_pacer_spaces_attempts_across_clients_and_includes_retries(monkeypatch):
    clock, starts = [100.0], []
    monkeypatch.setattr("investigation.llm.time.monotonic", lambda: clock[0])
    monkeypatch.setattr(
        "investigation.llm.time.sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds)
    )
    monkeypatch.setattr("investigation.llm.random.uniform", lambda low, high: 0)

    def handler(request):
        starts.append(clock[0])
        if len(starts) == 2:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json={})

    pacer = RequestPacer(12)
    config = settings().model_copy(update={"llm_max_retries": 1})
    clients = [
        LLMClient(config, transport=httpx.MockTransport(handler), pacer=pacer) for _ in range(2)
    ]
    try:
        for client in clients:
            client._post("https://provider.example/generate", {})
    finally:
        for client in clients:
            client.close()
    assert starts == [100, 112, 124]


def test_simplified_provider_schema_does_not_relax_local_claim_bounds():
    draft = {
        "status": "answered",
        "claims": [{"text": "x" * 2001, "evidence": [{"passage_id": "p1", "quote": "source"}]}],
    }
    client = LLMClient(
        settings(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=result([{"text": json.dumps(draft)}]))
        ),
    )
    try:
        with pytest.raises(ProviderError, match="invalid structured output"):
            client.synthesize(
                "Question?", [{"passage_id": "p1", "text": "source"}], ToolProposal(calls=[]), []
            )
    finally:
        client.close()


def test_verification_requires_explicit_conflict_decision_instead_of_defaulting_false():
    required = gemini_output_schema(Verification)["required"]
    assert "unresolved_conflict" in required and "unsupported_claim_indices" in required
    incomplete = {
        "answer_addresses_question": True,
        "reason": "The answer correctly reports a source conflict.",
    }
    client = LLMClient(
        settings(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=result([{"text": json.dumps(incomplete)}]))
        ),
    )
    try:
        with pytest.raises(ProviderError, match="invalid structured output"):
            client.verify("Question?", AnswerDraft(status="conflicting_evidence"), [])
    finally:
        client.close()


def result(parts, **extra):
    return {
        "candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3},
        **extra,
    }


def test_gemini_native_tools_roundtrip_preserves_model_content_and_uses_header_secret():
    requests = []
    original_content = {
        "role": "model",
        "parts": [
            {
                "functionCall": {
                    "id": "native-search-1",
                    "name": "search_documents",
                    "args": {"query": "Atlas timeout", "limit": 3},
                },
                "thoughtSignature": "opaque-provider-signature",
            }
        ],
    }

    def handler(request):
        requests.append(json.loads(request.content))
        assert request.headers["x-goog-api-key"] == "test-secret-never-in-url"
        assert "test-secret" not in str(request.url)
        assert request.url.path.endswith("fixture-model:generateContent")
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "candidates": [{"content": original_content}],
                    "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3},
                },
            )
        draft = {
            "status": "answered",
            "claims": [
                {
                    "text": "The timeout was 250 milliseconds.",
                    "evidence": [{"passage_id": "p1", "quote": "250 milliseconds"}],
                }
            ],
        }
        return httpx.Response(200, json=result([{"text": json.dumps(draft)}]))

    client = LLMClient(settings(), transport=httpx.MockTransport(handler))
    try:
        proposal = client.propose_tools("What was the Atlas timeout?")
        assert proposal.calls[0].arguments["query"] == "Atlas timeout"
        draft = client.synthesize(
            "What was the Atlas timeout?",
            [{"passage_id": "p1", "text": "The timeout was 250 milliseconds."}],
            proposal,
            [{"name": "search_documents", "result": {"passages": [{"passage_id": "p1"}]}}],
        )
        assert draft.status == "answered"
        assert requests[0]["toolConfig"]["functionCallingConfig"]["allowedFunctionNames"] == [
            "search_documents"
        ]
        assert requests[1]["contents"][1] == original_content
        assert requests[1]["contents"][0] == requests[0]["contents"][0]
        response = requests[1]["contents"][2]["parts"][0]["functionResponse"]
        assert response["name"] == "search_documents"
        assert response["id"] == "native-search-1"
        assert response["response"]["passages"][0]["passage_id"] == "p1"
        output_format = requests[1]["generationConfig"]["responseFormat"]["text"]
        assert output_format["mimeType"] == "APPLICATION_JSON"
        wire = output_format["schema"]
        assert wire["properties"]["status"]["enum"] == [
            "answered",
            "insufficient_evidence",
            "conflicting_evidence",
        ]
        claim = wire["properties"]["claims"]["items"]
        assert claim["required"] == ["text", "evidence"]
        assert claim["properties"]["evidence"]["items"]["properties"]["quote"] == {"type": "string"}
        assert "$ref" not in json.dumps(wire) and "maxItems" not in json.dumps(wire)
        assert client.usage == {"input_tokens": 14, "output_tokens": 6, "calls": 2, "retries": 0}
    finally:
        client.close()


def test_follow_up_receives_tool_evidence_before_choosing_next_search():
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=result(
                [
                    {
                        "functionCall": {
                            "name": "search_documents",
                            "args": {"query": "Orion team service catalog"},
                        }
                    }
                ]
            ),
        )

    client = LLMClient(settings(), transport=httpx.MockTransport(handler))
    try:
        proposal = ToolProposal(
            calls=[ToolCall(name="search_documents", arguments={"query": "Atlas incident"})],
            provider_content={
                "role": "model",
                "parts": [
                    {
                        "functionCall": {
                            "name": "search_documents",
                            "args": {"query": "Atlas incident"},
                        }
                    }
                ],
            },
        )
        follow_up = client.follow_up(
            "Which team owns the affected service?",
            proposal,
            [
                {
                    "name": "search_documents",
                    "result": {"passages": [{"text": "Atlas uses gateway."}]},
                }
            ],
        )
        assert follow_up.calls[0].arguments["query"] == "Orion team service catalog"
        assert payloads[0]["contents"][2]["parts"][0]["functionResponse"]["response"]["passages"]
    finally:
        client.close()


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503])
def test_provider_http_errors_are_typed_and_never_echo_secret_body(status):
    client = LLMClient(
        settings(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json={"error": "test-secret-never-in-url"})
        ),
    )
    try:
        with pytest.raises(ProviderError) as caught:
            client.propose_tools("Which service was affected?")
        assert "test-secret" not in str(caught.value)
    finally:
        client.close()


def test_timeout_is_bounded_and_secret_safe():
    def timeout(request):
        raise httpx.ReadTimeout("test-secret-never-in-url", request=request)

    client = LLMClient(settings(), transport=httpx.MockTransport(timeout))
    try:
        with pytest.raises(ProviderError, match="timeout") as caught:
            client.propose_tools("Which service was affected?")
        assert "test-secret" not in str(caught.value)
    finally:
        client.close()


def test_retry_after_is_capped_and_retry_count_is_reported(monkeypatch):
    attempts, waits = [], []

    def handler(request):
        attempts.append(request)
        if len(attempts) == 1:
            return httpx.Response(429, headers={"Retry-After": "999"})
        return httpx.Response(
            200,
            json=result(
                [{"functionCall": {"name": "search_documents", "args": {"query": "Atlas"}}}]
            ),
        )

    monkeypatch.setattr("investigation.llm.time.sleep", waits.append)
    monkeypatch.setattr("investigation.llm.random.uniform", lambda a, b: 0)
    configured = settings().model_copy(update={"llm_max_retries": 1})
    client = LLMClient(configured, transport=httpx.MockTransport(handler))
    try:
        assert client.propose_tools("Atlas incident").calls
        assert waits == [8]
        assert client.usage["retries"] == 1 and client.usage["calls"] == 1
    finally:
        client.close()


@pytest.mark.parametrize("reason", ["SAFETY", "RECITATION", "BLOCKLIST", "MAX_TOKENS"])
def test_blocked_or_truncated_answers_are_never_published(reason):
    response = {
        "candidates": [
            {"finishReason": reason, "content": {"parts": [{"text": "untrusted partial output"}]}}
        ]
    }
    client = LLMClient(
        settings(),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
    )
    try:
        with pytest.raises(ProviderError, match="blocked|incomplete"):
            client.propose_tools("Which service was affected?")
    finally:
        client.close()


@pytest.mark.parametrize(
    "response",
    [[], {"candidates": []}, {"candidates": [{"content": {"parts": [{"functionCall": {}}]}}]}],
)
def test_malformed_provider_envelopes_become_typed_errors(response):
    client = LLMClient(
        settings(),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
    )
    try:
        with pytest.raises(ProviderError):
            client.propose_tools("Which service was affected?")
    finally:
        client.close()


def test_invalid_structured_json_is_rejected_without_publishing_raw_model_text():
    response = result([{"text": '{"status":"answered","claims":"test-secret-never-in-url"}'}])
    client = LLMClient(
        settings(),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
    )
    try:
        with pytest.raises(ProviderError) as caught:
            client._structured("Test prompt", AnswerDraft)
        assert "test-secret" not in str(caught.value)
    finally:
        client.close()


@pytest.mark.parametrize("usage", ["missing", None, {}])
def test_missing_optional_usage_does_not_break_otherwise_valid_tool_response(usage):
    response = result([{"functionCall": {"name": "search_documents", "args": {"query": "Atlas"}}}])
    if usage == "missing":
        response.pop("usageMetadata")
    else:
        response["usageMetadata"] = usage
    client = LLMClient(
        settings(),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
    )
    try:
        assert client.propose_tools("Atlas incident").calls
        assert client.usage["input_tokens"] == 0
        assert client.usage["output_tokens"] == 0
    finally:
        client.close()


@pytest.mark.parametrize(
    "usage", [[], {"promptTokenCount": "secret-type-mismatch"}, {"promptTokenCount": -1}]
)
def test_malformed_usage_metadata_is_rejected_as_a_safe_provider_error(usage):
    response = result(
        [{"functionCall": {"name": "search_documents", "args": {"query": "Atlas"}}}],
        usageMetadata=usage,
    )
    client = LLMClient(
        settings(),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
    )
    try:
        with pytest.raises(ProviderError) as caught:
            client.propose_tools("Atlas incident")
        assert "secret-type-mismatch" not in str(caught.value)
    finally:
        client.close()


@pytest.mark.parametrize("text", [None, ["invalid", "text"], {"secret": "invalid content"}])
def test_non_string_structured_content_is_a_provider_error(text):
    client = LLMClient(
        settings(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=result([{"text": text}]))
        ),
    )
    try:
        with pytest.raises(ProviderError):
            client._structured("Test prompt", AnswerDraft)
    finally:
        client.close()


@pytest.mark.parametrize("message", [None, {"tool_calls": None}, {"tool_calls": [{}]}])
def test_malformed_ollama_tool_envelope_is_a_provider_error(message):
    configured = settings().model_copy(update={"llm_provider": "ollama"})
    client = LLMClient(
        configured,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"message": message})
        ),
    )
    try:
        with pytest.raises(ProviderError):
            client.propose_tools("Atlas incident")
    finally:
        client.close()


def test_upstream_protocol_disconnect_is_retried_then_reported_as_provider_error(monkeypatch):
    attempts = []
    monkeypatch.setattr("investigation.llm.time.sleep", lambda delay: None)

    def disconnect(request):
        attempts.append(1)
        raise httpx.RemoteProtocolError("secret provider diagnostic", request=request)

    configured = settings().model_copy(update={"llm_max_retries": 1})
    client = LLMClient(configured, transport=httpx.MockTransport(disconnect))
    try:
        with pytest.raises(ProviderError) as error:
            client.propose_tools("Atlas incident")
        assert len(attempts) == 2
        assert client.usage["retries"] == 1
        assert "secret" not in str(error.value)
    finally:
        client.close()

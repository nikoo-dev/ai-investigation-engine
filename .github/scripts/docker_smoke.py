"""Container lifecycle smoke: synthetic hash fixtures, no provider/model download."""

import os

import onnxruntime
from fastapi.testclient import TestClient

from investigation.config import Settings
from investigation.web import create_app

assert os.getuid() != 0, "The deployed image must run as its unprivileged user"
assert "CPUExecutionProvider" in onnxruntime.get_available_providers()
settings = Settings(
    environment="test",
    embedding_backend="hash",
    embedding_dimension=64,
    llm_provider="extractive",
    reranker_enabled=False,
)
settings.data_dir.mkdir(parents=True, exist_ok=True)
cache = settings.data_dir / "cache" / "models"
cache.mkdir(parents=True, exist_ok=True)
probe = cache / "smoke-write.txt"
probe.write_text("Container model cache is writable.\n", encoding="utf-8")
probe.unlink()

with TestClient(create_app(settings)) as client:
    assert client.get("/ready").status_code == 200
    first_boot = client.get("/health").json()["boot_id"]
    response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "container-source.txt",
                b"Atlas gateway is owned by the Orion team.",
                "text/plain",
            )
        },
    )
    assert response.status_code == 201, response.text
    document_id = response.json()["document"]["id"]
    answer = client.post(
        "/api/v1/investigations", json={"question": "Which team owns the Atlas gateway?"}
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["provider"] == "extractive"
    assert answer.json()["citations"]

with TestClient(create_app(settings)) as client:
    assert client.get("/health").json()["boot_id"] != first_boot
    document = client.get(f"/api/v1/documents/{document_id}")
    assert document.status_code == 200
    assert "Orion" in document.json()["text"]
    assert client.delete(f"/api/v1/documents/{document_id}").status_code == 204

print(
    "Nonroot container, ONNX runtime, writable cache, HTTP lifecycle and restart persistence passed."
)

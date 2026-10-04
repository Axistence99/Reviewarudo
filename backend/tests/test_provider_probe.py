import hashlib
import time
from unittest.mock import AsyncMock
import httpx
from fastapi.testclient import TestClient
from main import app, calls
from services import provider_probe as probe


def test_private_probe(monkeypatch):
    calls.clear()
    probe.results.clear()
    token = "private-test-capability"
    monkeypatch.setattr(probe, "TOKEN_HASH", hashlib.sha256(token.encode()).hexdigest())
    monkeypatch.setattr(probe, "EXPIRES", time.time() + 60)
    monkeypatch.setenv("GEMINI_API_KEY", "private-provider-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.return_value = httpx.Response(
        400,
        json={
            "error": {
                "message": "Invalid argument private-provider-key https://private.example 123456789 abcdefghijklmnopqrstuvwxyz0123456789"
            }
        },
    )
    monkeypatch.setattr(probe.httpx, "AsyncClient", lambda **kwargs: client)
    with TestClient(app) as browser:
        path = "/api/internal/provider-comparison"
        assert browser.post(path).status_code == 404
        assert client.post.await_count == 0
        headers = {"x-diagnostic-token": token}
        assert browser.post(path + "?mode=bad", headers=headers).status_code == 400
        first = browser.post(path, headers=headers)
        assert first.status_code == 200
        assert "Invalid argument" in first.text
        for secret in [
            "private-provider-key",
            "private.example",
            "123456789",
            "abcdefghijklmnopqrstuvwxyz0123456789",
        ]:
            assert secret not in first.text
        assert browser.post(path, headers=headers).json() == first.json()
        assert client.post.await_count == 1
        request = client.post.call_args.kwargs["json"]
        assert "generationConfig" not in request
        assert "synthetic.txt" in str(request)
        monkeypatch.setattr(probe, "EXPIRES", 0)
        assert browser.post(path, headers=headers).status_code == 404
        assert "provider-comparison" not in browser.get("/openapi.json").text
    calls.clear()
    probe.results.clear()

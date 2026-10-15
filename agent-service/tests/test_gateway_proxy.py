"""
The dashboard reads the live record through this service.

Without the pass-through the live-accuracy tile only worked when the whole app
was pointed at the gateway, so in production it was permanently a dash.
"""
import asyncio
import os
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402
from utils import gateway_proxy  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_cache():
    gateway_proxy.clear_cache()
    yield
    gateway_proxy.clear_cache()


@pytest.fixture
def client():
    return TestClient(app)


def _mock_gateway(monkeypatch, handler):
    """Route the proxy's outbound calls through an in-process handler."""
    calls = []
    real_client = httpx.AsyncClient

    def recording(request):
        calls.append(request)
        return handler(request)

    monkeypatch.setattr(gateway_proxy.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(recording), **kw))
    monkeypatch.setenv("GATEWAY_URL", "https://gateway.test/")
    return calls


def test_no_gateway_configured_is_a_404(client, monkeypatch):
    monkeypatch.delenv("GATEWAY_URL", raising=False)
    assert client.get("/api/gateway/accuracy").status_code == 404
    assert client.get("/api/gateway/predictions/recorded").status_code == 404


def test_recorded_predictions_are_forwarded_with_their_filters(client, monkeypatch):
    calls = _mock_gateway(monkeypatch, lambda r: httpx.Response(200, json={"count": 16}))

    response = client.get("/api/gateway/predictions/recorded?season=2026&week=5")

    assert response.status_code == 200
    assert response.json() == {"count": 16}
    assert calls[0].url.path == "/api/gateway/predictions/recorded"
    assert dict(calls[0].url.params) == {"season": "2026", "week": "5"}


def test_only_read_only_routes_are_exposed(client, monkeypatch):
    calls = _mock_gateway(monkeypatch, lambda r: httpx.Response(200, json={}))
    # Writes and agent fan-outs stay behind the gateway's token
    for path in ("/api/gateway/predictions/week/5", "/api/gateway/settle/run",
                 "/api/gateway/weights/refresh"):
        client.get(path)
        client.post(path)
    assert calls == []


def test_a_sleeping_gateway_is_paid_for_once(monkeypatch):
    calls = _mock_gateway(monkeypatch, lambda r: httpx.Response(200, json={"accuracy": 0.6}))

    async def twice():
        await gateway_proxy.fetch("/api/gateway/accuracy")
        return await gateway_proxy.fetch("/api/gateway/accuracy")

    assert asyncio.run(twice()) == {"accuracy": 0.6}
    assert len(calls) == 1


def test_an_upstream_error_is_not_cached_or_passed_through(client, monkeypatch):
    calls = _mock_gateway(monkeypatch, lambda r: httpx.Response(503, text="asleep"))

    assert client.get("/api/gateway/accuracy").status_code == 404
    assert client.get("/api/gateway/accuracy").status_code == 404
    assert len(calls) == 2, "a failure must be retried next time, not remembered"

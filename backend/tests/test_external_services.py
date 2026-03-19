import asyncio

import pytest

from src.gateway.services.external_services import _candidate_origins, _probe, _probe_service


def test_candidate_origins_add_local_aliases_for_host_style_urls():
    origins = _candidate_origins("http://host.docker.internal:8002")

    assert origins[0] == "http://host.docker.internal:8002"
    assert "http://127.0.0.1:8002" in origins
    assert "http://localhost:8002" in origins


def test_probe_service_falls_back_to_local_alias(monkeypatch):
    async def fake_probe(url: str, *, headers=None, timeout=2.5):
        if url == "http://127.0.0.1:8002/health":
            return True, None
        return False, "ConnectError"

    monkeypatch.setattr("src.gateway.services.external_services._probe", fake_probe)

    available, error, effective_origin = asyncio.run(_probe_service("http://host.docker.internal:8002", "/health"))

    assert available is True
    assert error is None
    assert effective_origin == "http://127.0.0.1:8002"


def test_probe_returns_exception_class_when_message_is_blank(monkeypatch):
    class SilentBoom(Exception):
        def __str__(self) -> str:
            return ""

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url: str, headers=None):
            raise SilentBoom()

    monkeypatch.setattr("src.gateway.services.external_services.httpx.AsyncClient", FakeClient)

    available, error = asyncio.run(_probe("http://host.docker.internal:8002/health"))

    assert available is False
    assert error == "SilentBoom"

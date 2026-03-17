"""Unit tests for MiroThinker community tools (Tier 2 and Tier 3)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import src.community.mirothinker.tools as mt_tools
import src.community.mirothinker.miroflow_tool as mf_tool


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

class _FakeResp:
    status_code = 200

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


# ---------------------------------------------------------------------------
# mirothinker_research_tool (Tier 2 — direct Ollama)
# ---------------------------------------------------------------------------

class TestMiroThinkerResearchTool:
    def test_returns_structured_json(self):
        fake_resp = _FakeResp({
            "choices": [{"message": {"content": "Deep analysis here."}}]
        })
        with patch("src.community.mirothinker.tools.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = fake_resp
            mock_client_cls.return_value = mock_client

            result = mt_tools.mirothinker_research_tool.invoke({"query": "Explain quantum entanglement", "depth": "quick"})

        import json
        data = json.loads(result)
        assert "MiroThinker" in data["source"]
        assert data["depth"] == "quick"
        assert "Deep analysis here." in data["analysis"]

    def test_invalid_depth_normalized(self):
        fake_resp = _FakeResp({
            "choices": [{"message": {"content": "Analysis."}}]
        })
        with patch("src.community.mirothinker.tools.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = fake_resp
            mock_client_cls.return_value = mock_client

            # "invalid" depth should be normalized to "standard"
            result = mt_tools.mirothinker_research_tool.invoke({"query": "test", "depth": "invalid"})

        import json
        data = json.loads(result)
        assert data["depth"] == "standard"

    def test_timeout_returns_error_message(self):
        import httpx
        with patch("src.community.mirothinker.tools.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.TimeoutException("timeout")
            mock_client_cls.return_value = mock_client

            result = mt_tools.mirothinker_research_tool.invoke({"query": "test", "depth": "standard"})

        assert "timed out" in result.lower() or "timeout" in result.lower()

    def test_empty_response_handled(self):
        fake_resp = _FakeResp({"choices": [{"message": {"content": ""}}]})
        with patch("src.community.mirothinker.tools.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = fake_resp
            mock_client_cls.return_value = mock_client

            result = mt_tools.mirothinker_research_tool.invoke({"query": "test"})

        assert "empty" in result.lower() or "returned" in result.lower()


# ---------------------------------------------------------------------------
# miroflow_research_tool (Tier 3 — MiroFlow wrapper)
# ---------------------------------------------------------------------------

class TestMiroFlowResearchTool:
    def test_returns_result_when_server_healthy(self):
        health_resp = _FakeResp({"status": "ok", "miroflow_available": True, "model": "mirothinker-v2:latest"})
        research_resp = _FakeResp({
            "result": "MiroFlow deep analysis.",
            "mode": "miroflow",
            "model": "mirothinker-v2:latest",
        })

        with patch("src.community.mirothinker.miroflow_tool.httpx.get", return_value=health_resp), \
             patch("src.community.mirothinker.miroflow_tool.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = research_resp
            mock_client_cls.return_value = mock_client

            result = mf_tool.miroflow_research_tool.invoke({"query": "Analyze AI trends", "max_turns": 10})

        import json
        data = json.loads(result)
        assert "MiroFlow" in data["source"]
        assert "MiroFlow deep analysis." in data["result"]

    def test_returns_error_when_server_unreachable(self):
        import httpx
        with patch("src.community.mirothinker.miroflow_tool.httpx.get", side_effect=httpx.ConnectError("refused")):
            result = mf_tool.miroflow_research_tool.invoke({"query": "test", "max_turns": 5})

        assert "not reachable" in result.lower() or "error" in result.lower()

    def test_max_turns_clamped(self):
        health_resp = _FakeResp({"status": "ok"})
        research_resp = _FakeResp({"result": "ok", "mode": "miroflow", "model": "m"})

        captured_payload = {}

        def fake_post(url, json=None, **kwargs):
            captured_payload.update(json or {})
            return research_resp

        with patch("src.community.mirothinker.miroflow_tool.httpx.get", return_value=health_resp), \
             patch("src.community.mirothinker.miroflow_tool.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = fake_post
            mock_client_cls.return_value = mock_client

            # 500 > max allowed (300) — should be clamped
            mf_tool.miroflow_research_tool.invoke({"query": "test", "max_turns": 500})

        assert captured_payload.get("max_turns", 0) <= 300

        captured_payload.clear()
        with patch("src.community.mirothinker.miroflow_tool.httpx.get", return_value=health_resp), \
             patch("src.community.mirothinker.miroflow_tool.httpx.Client") as mock_client_cls2:
            mock_client2 = MagicMock()
            mock_client2.__enter__ = MagicMock(return_value=mock_client2)
            mock_client2.__exit__ = MagicMock(return_value=False)
            mock_client2.post.side_effect = fake_post
            mock_client_cls2.return_value = mock_client2

            # 0 < min (1) — should be clamped
            mf_tool.miroflow_research_tool.invoke({"query": "test", "max_turns": 0})

        assert captured_payload.get("max_turns", 0) >= 1

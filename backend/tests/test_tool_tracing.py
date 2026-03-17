from __future__ import annotations

import asyncio
from contextlib import contextmanager

from langchain_core.tools import StructuredTool

from src.tools.tools import _wrap_tool_with_tracing


def test_wrap_tool_with_tracing_supports_structured_tool(monkeypatch):
    observed: list[str] = []

    @contextmanager
    def fake_observe_span(name: str, **_: object):
        observed.append(name)
        yield

    monkeypatch.setattr("src.observability.observe_span", fake_observe_span)

    tool = StructuredTool.from_function(
        func=lambda value: f"echo:{value}",
        name="echo_tool",
        description="Echo the provided value.",
    )

    wrapped = _wrap_tool_with_tracing(tool)

    assert wrapped.invoke({"value": "ok"}) == "echo:ok"
    assert observed == ["tool.echo_tool"]


def test_wrap_tool_with_tracing_is_idempotent(monkeypatch):
    observed: list[str] = []

    @contextmanager
    def fake_observe_span(name: str, **_: object):
        observed.append(name)
        yield

    monkeypatch.setattr("src.observability.observe_span", fake_observe_span)

    async def _uppercase(value: str) -> str:
        return value.upper()

    tool = StructuredTool.from_function(
        coroutine=_uppercase,
        name="upper_tool",
        description="Uppercase the provided value.",
    )

    wrapped_once = _wrap_tool_with_tracing(tool)
    wrapped_twice = _wrap_tool_with_tracing(wrapped_once)

    assert wrapped_once is wrapped_twice
    assert asyncio.run(wrapped_twice.ainvoke({"value": "ok"})) == "OK"
    assert observed == ["tool.upper_tool"]

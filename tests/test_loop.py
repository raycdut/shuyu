"""Tests for agent/loop.py — ReAct agent loop with mocked LLM and tools."""

from __future__ import annotations

import json

import pytest

from app.agent.loop import AgentLoop
from app.agent.tools.registry import Tool, ToolRegistry


@pytest.fixture
def tool_registry():
    reg = ToolRegistry()

    async def echo_handler(text: str) -> str:
        return f"ECHO: {text}"

    reg.register(Tool(
        name="echo",
        description="回显",
        parameters={"text": {"type": "string"}},
        handler=echo_handler,
    ))

    async def add_handler(a: int, b: int) -> str:
        return str(a + b)

    reg.register(Tool(
        name="add",
        description="加法",
        parameters={"a": {"type": "int"}, "b": {"type": "int"}},
        handler=add_handler,
    ))
    return reg


@pytest.mark.asyncio
async def test_direct_answer_no_tool_call(tool_registry):
    """If LLM responds without tool calls, return content directly."""

    async def mock_llm(**kw):
        class FakeMsg:
            content = "你好！我是助手。"
            tool_calls = None
        class FakeChoice:
            message = FakeMsg()
        class FakeResp:
            choices = [FakeChoice()]
        return FakeResp()

    loop = AgentLoop(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    result = await loop.run([{"role": "user", "content": "你好"}])
    assert result["content"] == "你好！我是助手。"


@pytest.mark.asyncio
async def test_single_tool_call(tool_registry):
    """If LLM calls a tool, execute it and return result."""

    async def mock_llm(**kw):
        # Extract messages to determine what to return
        msgs = kw.get("messages", [])
        last = msgs[-1]["content"] if msgs else ""
        tool_role = msgs[-1].get("role") if msgs else ""

        class FakeChoice:
            class FakeMsg:
                content = ""
                tool_calls = None
            def __init__(self):
                self.message = self.FakeMsg()

        # First call: return tool call
        if tool_role == "user" or (not tool_role):
            fc = FakeChoice()
            fc.message.content = ""
            fc.message.tool_calls = [
                type("TC", (), {
                    "id": "call-1",
                    "function": type("F", (), {
                        "name": "echo",
                        "arguments": json.dumps({"text": "hello"}),
                    })(),
                })()
            ]
            return type("R", (), {"choices": [fc]})()

        # After tool result: return final answer
        return type("R", (), {"choices": [type("C", (), {
            "message": type("M", (), {"content": "ECHO: hello", "tool_calls": None})()
        })()]})()

    loop = AgentLoop(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    result = await loop.run([{"role": "user", "content": "echo hello"}])
    assert "ECHO: hello" in result["content"]


@pytest.mark.asyncio
async def test_max_iterations(tool_registry):
    """Should stop after max_iterations and return timeout message."""

    call_count = 0

    async def infinite_llm(**kw):
        nonlocal call_count
        call_count += 1
        class FC:
            content = ""
            tool_calls = [
                type("TC", (), {
                    "id": f"call-{call_count}",
                    "function": type("F", (), {
                        "name": "echo",
                        "arguments": json.dumps({"text": "loop"}),
                    })(),
                })()
            ]
        return type("R", (), {"choices": [type("C", (), {"message": FC()})()]})()

    loop = AgentLoop(
        tool_registry=tool_registry,
        call_llm_func=infinite_llm,
        system_prompt="助手",
        max_iterations=3,
    )
    result = await loop.run([{"role": "user", "content": "loop"}])
    assert "抱歉" in result["content"] or "太久" in result["content"]


@pytest.mark.asyncio
async def test_tool_call_json_error(tool_registry):
    """Bad JSON in tool arguments should be handled gracefully."""

    async def bad_json_llm(**kw):
        class FC:
            content = ""
            tool_calls = [
                type("TC", (), {
                    "id": "call-1",
                    "function": type("F", (), {
                        "name": "echo",
                        "arguments": "{bad json",
                    })(),
                })()
            ]
        return type("R", (), {"choices": [type("C", (), {"message": FC()})()]})()

    async def final_llm(**kw):
        class FC:
            content = "done"
            tool_calls = None
        return type("R", (), {"choices": [type("C", (), {"message": FC()})()]})()

    # First call bad json, second call final answer
    call_log = []
    async def combined_llm(**kw):
        call_log.append(1)
        if len(call_log) == 1:
            return await bad_json_llm(**kw)
        return await final_llm(**kw)

    loop = AgentLoop(tool_registry=tool_registry, call_llm_func=combined_llm, system_prompt="助手")
    result = await loop.run([{"role": "user", "content": "hi"}])
    assert result["content"] == "done"

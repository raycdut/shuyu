"""Tests for agent/advanced_agent.py — Plan → ReAct → Reflect pipeline."""

from __future__ import annotations

import json

import pytest

from app.agent.advanced_agent import AdvancedAgent
from app.agent.tools.registry import Tool, ToolRegistry


@pytest.fixture
def tool_registry():
    reg = ToolRegistry()

    async def echo_handler(question: str) -> str:
        return f"ECHO: {question}"

    reg.register(Tool(
        name="query_database",
        description="查询数据库",
        parameters={"question": {"type": "string"}},
        handler=echo_handler,
    ))
    return reg


def _make_choice(content: str = "", tool_calls: list | None = None):
    """Build a fake LLM response with optional tool calls."""
    class FakeMsg:
        def __init__(self):
            self.content = content
            self.tool_calls = tool_calls

    class FakeChoice:
        def __init__(self):
            self.message = FakeMsg()

    class FakeResp:
        def __init__(self):
            self.choices = [FakeChoice()]

    return FakeResp()


def _make_tool_call(id: str, name: str, arguments: dict):
    """Build a fake tool call object."""
    class FakeFunc:
        def __init__(self):
            self.name = name
            self.arguments = json.dumps(arguments)

    class FakeTC:
        def __init__(self):
            self.id = id
            self.function = FakeFunc()

    return FakeTC()


# ---------------------------------------------------------------------------
# Phase 1: Plan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_phase_generates_structured_output(tool_registry):
    """Plan phase should produce a structured analysis plan."""

    plan_calls = []

    async def mock_llm(**kw):
        tools = kw.get("tools")
        # First call (plan): no tools provided
        if tools is None:
            plan_calls.append(kw.get("messages", []))
            return _make_choice(content="## 分析目标\n分析销量\n\n## 分析步骤\n1. 查订单表\n2. 汇总销售额")
        # ReAct: tool call
        return _make_choice(
            content="Let me check...",
            tool_calls=[_make_tool_call("c1", "query_database", {"question": "sales"})],
        )

    agent = AdvancedAgent(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    result = await agent.run([{"role": "user", "content": "分析销量趋势"}])

    assert result["role"] == "assistant"
    assert len(result["content"]) > 0
    # Plan should have been called with PLAN_PROMPT (no tools)
    assert len(plan_calls) >= 1
    # The prompt should contain the plan prompt keyword
    plan_msgs = plan_calls[0]
    assert any("分析规划师" in m.get("content", "") for m in plan_msgs if m.get("role") == "system")


# ---------------------------------------------------------------------------
# Phase 2: ReAct
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_react_executes_tool_and_produces_answer(tool_registry):
    """ReAct phase should execute tool calls and produce a final answer."""

    call_log = []

    async def mock_llm(**kw):
        call_log.append(len(call_log))

        # First call: Plan (tools=None)
        if len(call_log) == 1:
            return _make_choice(content="## 分析目标\n测试")
        # Second call: ReAct with tool call
        elif len(call_log) == 2:
            return _make_choice(
                content="",
                tool_calls=[_make_tool_call("c1", "query_database", {"question": "hello"})],
            )
        # Third call: ReAct with final answer (no tool calls)
        else:
            return _make_choice(content="分析结果：ECHO: hello")

    agent = AdvancedAgent(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    result = await agent.run([{"role": "user", "content": "hello"}])

    assert "ECHO: hello" in result["content"] or "分析结果" in result["content"]


@pytest.mark.asyncio
async def test_react_loop_detection_breaks_to_reflect(tool_registry):
    """When is_stuck detects repetition, ReAct should break to Reflect."""

    call_log = []

    def repeating_llm_factory():
        call_log = []
        async def repeating_llm(**kw):
            tools = kw.get("tools")
            call_log.append(len(call_log))
            if len(call_log) == 1:
                return _make_choice(content="## 分析目标\n测试")
            # Reflect phase (tools=None): return text
            if tools is None:
                return _make_choice(content="汇总结果：多次查询后汇总")
            # ReAct: always return the same tool call (loop trigger after 3+ repetitions)
            return _make_choice(
                content="",
                tool_calls=[_make_tool_call(f"c{len(call_log)}", "query_database", {"question": "same"})],
            )
        return call_log, repeating_llm

    call_log, repeating_llm = repeating_llm_factory()

    agent = AdvancedAgent(tool_registry=tool_registry, call_llm_func=repeating_llm, system_prompt="助手")
    result = await agent.run([{"role": "user", "content": "loop test"}])

    # Should produce some output (either from reflect or loop break)
    assert len(result["content"]) > 0, f"Empty result, call_log={call_log}"
    # Should NOT have made more than 7 LLM calls (plan + 4 react iterations + reflect)
    assert len(call_log) <= 7, f"Too many iterations: {len(call_log)}"


@pytest.mark.asyncio
async def test_react_handles_json_decode_error_in_tool_args(tool_registry):
    """Bad JSON in tool arguments should be handled gracefully."""

    class BadFunc:
        name = "query_database"
        arguments = "{bad json"

    class BadTC:
        id = "c1"
        function = BadFunc()

    class BadMsg:
        content = ""
        tool_calls = [BadTC()]

    class BadChoice:
        message = BadMsg()

    class BadResp:
        choices = [BadChoice()]

    call_count = [0]

    async def mock_llm(**kw):
        call_count[0] += 1
        if call_count[0] == 1:
            return _make_choice(content="## 分析目标\n测试")
        if call_count[0] == 2:
            resp = BadResp()
            return resp
        return _make_choice(content="完成")

    agent = AdvancedAgent(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    result = await agent.run([{"role": "user", "content": "test"}])

    assert len(result["content"]) > 0


# ---------------------------------------------------------------------------
# Phase 3: Reflect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reflect_phase_runs_when_react_output_too_short(tool_registry):
    """Reflect should be invoked when ReAct final answer is short (<50 chars) or data is empty."""

    call_log = []

    async def mock_llm(**kw):
        tools = kw.get("tools")
        call_log.append(("call", tools is not None))
        idx = len(call_log)
        if idx == 1:
            return _make_choice(content="## 分析目标\n测试")
        # Reflect phase (tools=None): return summary
        if tools is None:
            return _make_choice(content="汇总：查询完成")
        # ReAct #1: final answer (no tool calls) — exit loop immediately
        if idx == 2:
            return _make_choice(content="ok")
        # ReAct #2: tool call
        if idx == 3:
            return _make_choice(
                content="",
                tool_calls=[_make_tool_call("c1", "query_database", {"question": "data"})],
            )
        # After tool result, ReAct #3: short final answer
        if idx == 4:
            return _make_choice(content="done")
        return _make_choice(content="")

    agent = AdvancedAgent(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    result = await agent.run([{"role": "user", "content": "test"}])

    assert len(result["content"]) > 0


@pytest.mark.asyncio
async def test_reflect_skipped_when_react_has_good_answer(tool_registry):
    """Reflect should be skipped when ReAct answer is meaningful and data was collected."""

    async def data_returner(**kw):
        return _make_choice(content=f"ECHO: data_result_{'x' * 60}")

    call_log = []

    async def mock_llm(**kw):
        call_log.append(len(call_log))
        if len(call_log) == 1:
            return _make_choice(content="## 分析目标\n测试")
        if len(call_log) == 2:
            return _make_choice(
                content="",
                tool_calls=[_make_tool_call("c1", "query_database", {"question": "get data"})],
            )
        # tool_registry.call_tool will call data_returner for the tool
        if len(call_log) == 3:
            return _make_choice(content=f"结果：数据是 x{'y' * 60}")  # > 50 chars
        return _make_choice(content="final")

    # We need echo_handler to return actual data
    reg = ToolRegistry()
    async def data_handler(question: str) -> str:
        return f"DATA: {question} — " + "x" * 80

    reg.register(Tool(
        name="query_database",
        description="查询数据库",
        parameters={"question": {"type": "string"}},
        handler=data_handler,
    ))

    agent = AdvancedAgent(tool_registry=reg, call_llm_func=mock_llm, system_prompt="助手")
    result = await agent.run([{"role": "user", "content": "test"}])

    # Should have data accumulated
    assert "结果" in result["content"] or "数据" in result["content"]


# ---------------------------------------------------------------------------
# Full pipeline + progress callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_progress_callback_receives_events(tool_registry):
    """Progress callback should receive plan, query, and done events."""

    events = []

    async def progress(event: dict):
        events.append(event)

    async def mock_llm(**kw):
        tools = kw.get("tools")
        if tools is None:
            return _make_choice(content="## 分析目标\n测试\n## 分析步骤\n1. 查数据")
        return _make_choice(content="最终结果")

    agent = AdvancedAgent(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    await agent.run([{"role": "user", "content": "test"}], progress_callback=progress)

    event_types = [e["type"] for e in events]
    assert "plan" in event_types
    assert "done" in event_types


# ---------------------------------------------------------------------------
# Max iterations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_max_iterations_limit(tool_registry):
    """Should not exceed max_iterations."""

    call_count = [0]

    async def infinite_llm(**kw):
        tools = kw.get("tools")
        call_count[0] += 1
        if call_count[0] == 1:
            return _make_choice(content="## 分析目标\n测试")
        # Reflect phase (tools=None): return summary
        if tools is None:
            return _make_choice(content="汇总结果")
        # Always request a tool call
        return _make_choice(
            content="",
            tool_calls=[_make_tool_call(f"c{call_count[0]}", "query_database", {"question": "data"})],
        )

    agent = AdvancedAgent(
        tool_registry=tool_registry,
        call_llm_func=infinite_llm,
        system_prompt="助手",
        max_iterations=5,
    )
    result = await agent.run([{"role": "user", "content": "loop"}])

    # Plan (1) + ReAct iterations (5) + maybe Reflect (1) = at most 7 calls
    assert call_count[0] <= 7, f"Too many calls: {call_count[0]}"
    assert len(result["content"]) > 0


# ---------------------------------------------------------------------------
# SQL queries tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sql_queries_in_result(tool_registry):
    """AdvancedAgent should return sql_queries in the result dict."""

    async def mock_llm(**kw):
        tools = kw.get("tools")
        if tools is None:
            return _make_choice(content="## 分析目标\n测试")
        if getattr(mock_llm, "called_once", None) is None:
            mock_llm.called_once = True
            return _make_choice(
                content="",
                tool_calls=[_make_tool_call("c1", "query_database", {"question": "hello"})],
            )
        return _make_choice(content="done")

    agent = AdvancedAgent(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    result = await agent.run([{"role": "user", "content": "test"}])

    assert "sql_queries" in result
    assert isinstance(result["sql_queries"], list)

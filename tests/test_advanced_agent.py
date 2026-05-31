"""Tests for agent/advanced_agent.py — Plan → Reflect → Execute → Report → Reflect pipeline."""

from __future__ import annotations

import json

import pytest

from app.agent.advanced_agent import AdvancedAgent
from app.agent.tools.registry import Tool, ToolRegistry


@pytest.fixture
def tool_registry():
    reg = ToolRegistry()

    async def echo_handler(question: str) -> str:
        return f"ECHO: {question} — " + "x" * 80

    reg.register(Tool(
        name="query_database",
        description="查询数据库",
        parameters={"question": {"type": "string"}},
        handler=echo_handler,
    ))
    return reg


def _make_choice(content: str = "", tool_calls: list | None = None):
    """Build a fake LLM response."""
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


def _sys_content(msgs: list) -> str:
    """Extract system prompt content from messages."""
    for m in msgs:
        if m.get("role") == "system":
            return m.get("content", "")
    return ""


# ---------------------------------------------------------------------------
# Plan phase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_count_minimum(tool_registry):
    """Pipeline should make at least 5 LLM calls for plan, reflect, execute, report, report_reflect."""

    call_count = [0]

    async def mock_llm(**kw):
        call_count[0] += 1
        tools = kw.get("tools")
        sys_prompt = _sys_content(kw.get("messages", []))

        if tools is None and "分析规划师" in sys_prompt:
            return _make_choice(content='{"target": "测试", "steps": [{"purpose": "查数据", "sql": "SELECT 1"}]}')
        if tools is None and "审核专家" in sys_prompt:
            return _make_choice(content='{"verdict": "合理", "issues": [], "suggestions": []}')
        if tools is None and "报告撰写专家" in sys_prompt:
            return _make_choice(content="报告：完成")
        if tools is None and "报告审核专家" in sys_prompt:
            return _make_choice(content='{"verdict": "通过", "issues": [], "suggestions": [], "needs_new_plan": false}')
        return _make_choice(content="数据 OK")

    agent = AdvancedAgent(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    result = await agent.run([{"role": "user", "content": "test"}])

    assert len(result["content"]) > 0
    assert call_count[0] >= 5


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_produces_result(tool_registry):
    """Full pipeline should produce a non-empty result."""

    call_count = [0]

    async def mock_llm(**kw):
        call_count[0] += 1
        tools = kw.get("tools")
        sys_prompt = _sys_content(kw.get("messages", []))

        if tools is None and "分析规划师" in sys_prompt:
            return _make_choice(content='{"target": "测试", "steps": [{"purpose": "查数据", "sql": "SELECT 1"}]}')
        if tools is None and "审核专家" in sys_prompt:
            return _make_choice(content='{"verdict": "合理", "issues": [], "suggestions": []}')
        if tools is None and "报告撰写专家" in sys_prompt:
            return _make_choice(content="报告：完成")
        if tools is None and "报告审核专家" in sys_prompt:
            return _make_choice(content='{"verdict": "通过", "issues": [], "suggestions": [], "needs_new_plan": false}')
        # Execute step - return data directly (no tool calls, >30 chars)
        return _make_choice(content="销售数据：100件商品，总额50000元")

    agent = AdvancedAgent(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    result = await agent.run([{"role": "user", "content": "test"}])

    assert len(result["content"]) > 0


@pytest.mark.asyncio
async def test_progress_callback_receives_events(tool_registry):
    """Progress callback should receive all event types."""

    events = []

    async def progress(event: dict):
        events.append(event)

    call_count = [0]

    async def mock_llm(**kw):
        call_count[0] += 1
        tools = kw.get("tools")
        sys_prompt = _sys_content(kw.get("messages", []))

        if tools is None and "分析规划师" in sys_prompt:
            return _make_choice(content='{"target": "测试", "steps": [{"purpose": "查数据", "sql": "SELECT 1"}]}')
        if tools is None and "审核专家" in sys_prompt:
            return _make_choice(content='{"verdict": "合理", "issues": [], "suggestions": []}')
        if tools is None and "报告撰写专家" in sys_prompt:
            return _make_choice(content="报告：最终")
        if tools is None and "报告审核专家" in sys_prompt:
            return _make_choice(content='{"verdict": "通过", "issues": [], "suggestions": [], "needs_new_plan": false}')
        return _make_choice(content="数据 OK")

    agent = AdvancedAgent(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    await agent.run([{"role": "user", "content": "test"}], progress_callback=progress)

    event_types = [e["type"] for e in events]
    assert "plan" in event_types
    assert "done" in event_types


# ---------------------------------------------------------------------------
# SQL queries tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sql_queries_in_result(tool_registry):
    """AdvancedAgent should return sql_queries in the result dict."""

    call_count = [0]

    async def mock_llm(**kw):
        call_count[0] += 1
        tools = kw.get("tools")
        sys_prompt = _sys_content(kw.get("messages", []))

        if tools is None and "分析规划师" in sys_prompt:
            return _make_choice(content='{"target": "测试", "steps": [{"purpose": "查数据", "sql": "SELECT 1"}]}')
        if tools is None and "审核专家" in sys_prompt:
            return _make_choice(content='{"verdict": "合理", "issues": [], "suggestions": []}')
        if tools is None and "报告撰写专家" in sys_prompt:
            return _make_choice(content="报告")
        if tools is None and "报告审核专家" in sys_prompt:
            return _make_choice(content='{"verdict": "通过", "issues": [], "suggestions": [], "needs_new_plan": false}')
        return _make_choice(content="数据 OK")

    agent = AdvancedAgent(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    result = await agent.run([{"role": "user", "content": "test"}])

    assert "sql_queries" in result
    assert isinstance(result["sql_queries"], list)


# ---------------------------------------------------------------------------
# Plan reflection loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_reflection_loops_on_revision(tool_registry):
    """Plan reflection should loop when plan is rejected."""

    call_count = [0]

    async def mock_llm(**kw):
        call_count[0] += 1
        tools = kw.get("tools")
        sys_prompt = _sys_content(kw.get("messages", []))

        if tools is None and "分析规划师" in sys_prompt:
            return _make_choice(content='{"target": "测试", "steps": [{"purpose": "查数据", "sql": "SELECT 1"}]}')
        # Return "需要修改" for the first two reflection calls, then "合理"
        if tools is None and "审核专家" in sys_prompt:
            if call_count[0] <= 3:
                return _make_choice(content='{"verdict": "需要修改", "issues": ["缺少表关联"], "suggestions": ["加 JOIN"]}')
            return _make_choice(content='{"verdict": "合理", "issues": [], "suggestions": []}')
        if tools is None and "报告撰写专家" in sys_prompt:
            return _make_choice(content="报告")
        if tools is None and "报告审核专家" in sys_prompt:
            return _make_choice(content='{"verdict": "通过", "issues": [], "suggestions": [], "needs_new_plan": false}')
        return _make_choice(content="数据 OK")

    agent = AdvancedAgent(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    result = await agent.run([{"role": "user", "content": "test"}])

    assert len(result["content"]) > 0
    # Plan review was rejected, so plan was regenerated at least once
    assert call_count[0] >= 6  # plan + 2 plan_reflect + 2 plan_regen + ... + report + report_reflect


# ---------------------------------------------------------------------------
# Error handling: JSON decode error in tool args
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handles_json_decode_error_in_tool_args(tool_registry):
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
        tools = kw.get("tools")
        sys_prompt = _sys_content(kw.get("messages", []))

        if tools is None and "分析规划师" in sys_prompt:
            return _make_choice(content='{"target": "测试", "steps": [{"purpose": "查数据", "sql": "SELECT 1"}]}')
        if tools is None and "审核专家" in sys_prompt:
            return _make_choice(content='{"verdict": "合理", "issues": [], "suggestions": []}')
        if tools is None and "报告撰写专家" in sys_prompt:
            return _make_choice(content="报告")
        if tools is None and "报告审核专家" in sys_prompt:
            return _make_choice(content="审核结论：通过")
        if call_count[0] == 3:  # First execute call with bad JSON
            resp = BadResp()
            return resp
        return _make_choice(content="数据 OK")

    agent = AdvancedAgent(tool_registry=tool_registry, call_llm_func=mock_llm, system_prompt="助手")
    result = await agent.run([{"role": "user", "content": "test"}])

    assert len(result["content"]) > 0


# ---------------------------------------------------------------------------
# Max iterations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_max_iterations_limit(tool_registry):
    """Should still produce output (max_iterations is for ReAct sub-loop)."""

    call_count = [0]

    async def mock_llm(**kw):
        call_count[0] += 1
        tools = kw.get("tools")
        sys_prompt = _sys_content(kw.get("messages", []))

        if tools is None and "分析规划师" in sys_prompt:
            return _make_choice(content='{"target": "测试", "steps": [{"purpose": "查数据", "sql": "SELECT 1"}]}')
        if tools is None and "审核专家" in sys_prompt:
            return _make_choice(content='{"verdict": "合理", "issues": [], "suggestions": []}')
        if tools is None and "报告撰写专家" in sys_prompt:
            return _make_choice(content="报告：最终结果")
        if tools is None and "报告审核专家" in sys_prompt:
            return _make_choice(content="审核结论：通过")
        return _make_choice(content="数据 OK")

    agent = AdvancedAgent(
        tool_registry=tool_registry,
        call_llm_func=mock_llm,
        system_prompt="助手",
        max_iterations=5,
    )
    result = await agent.run([{"role": "user", "content": "test"}])

    assert len(result["content"]) > 0

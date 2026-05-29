"""Tests for agent/tools/registry.py — Tool, ToolRegistry."""

from __future__ import annotations

import pytest

from app.agent.tools.registry import Tool, ToolRegistry


class TestTool:
    def test_basic(self):
        async def handler(x: int) -> str:
            return f"got {x}"

        t = Tool(name="echo", description="echoes", parameters={"x": {"type": "int"}}, handler=handler)
        assert t.name == "echo"
        assert t.description == "echoes"
        assert t.required == ["x"]

    def test_custom_required(self):
        async def handler(a: str, b: str) -> str:
            return f"{a}{b}"

        t = Tool(name="concat", description="", parameters={"a": {}, "b": {}}, handler=handler, required=["a"])
        assert t.required == ["a"]

    def test_to_openai_tool(self):
        async def handler(x: int) -> str:
            return f"{x}"

        t = Tool(name="calc", description="计算", parameters={"x": {"type": "int"}}, handler=handler)
        oa = t.to_openai_tool()
        assert oa["type"] == "function"
        assert oa["function"]["name"] == "calc"
        assert oa["function"]["parameters"]["required"] == ["x"]


class TestToolRegistry:
    @pytest.fixture
    def registry(self):
        return ToolRegistry()

    @pytest.fixture
    def sample_tool(self):
        async def handler(q: str) -> str:
            return f"result:{q}"
        return Tool(name="query", description="查询", parameters={"q": {}}, handler=handler)

    def test_register_and_get(self, registry, sample_tool):
        registry.register(sample_tool)
        assert registry.get("query") is sample_tool
        assert registry.get("nonexistent") is None

    def test_list_tools(self, registry, sample_tool):
        registry.register(sample_tool)
        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "query"

    def test_to_openai_tools(self, registry, sample_tool):
        registry.register(sample_tool)
        tools = registry.to_openai_tools()
        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "query"

    @pytest.mark.asyncio
    async def test_call_tool_success(self, registry, sample_tool):
        registry.register(sample_tool)
        result = await registry.call_tool("query", {"q": "hello"})
        assert result == "result:hello"

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self, registry):
        result = await registry.call_tool("missing", {})
        assert "未找到" in result

    @pytest.mark.asyncio
    async def test_call_tool_error(self, registry):
        async def bad_handler(**kw):
            raise ValueError("boom")
        registry.register(Tool(name="bad", description="", parameters={}, handler=bad_handler))
        result = await registry.call_tool("bad", {})
        assert "执行出错" in result
        assert "boom" in result

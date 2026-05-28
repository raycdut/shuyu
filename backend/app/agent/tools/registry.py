"""Tool registry — extensible system for adding tools to the agent."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

ToolFunc = Callable[..., Coroutine[Any, Any, str]]


class Tool:
    """A tool that the agent can call."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: ToolFunc,
        required: list[str] = None,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self.required = required or list(parameters.keys())

    def to_openai_tool(self) -> dict:
        """Format as OpenAI-compatible tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }


class ToolRegistry:
    """Manages all tools available to the agent."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def to_openai_tools(self) -> list[dict]:
        return [t.to_openai_tool() for t in self._tools.values()]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool and return its result as text."""
        tool = self.get(name)
        if not tool:
            return f"错误：未找到工具 '{name}'"

        try:
            return await tool.handler(**arguments)
        except Exception as e:
            return f"工具 '{name}' 执行出错：{e}"

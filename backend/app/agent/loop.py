"""ReAct Agent Loop — self-built, no framework.

The agent:
1. Receives a user message
2. Decides whether to call a tool or respond directly
3. If calling a tool: executes it, observes the result, repeats from 2
4. If responding: formats and returns the answer
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from .tools.registry import ToolRegistry


class AgentLoop:
    """Simple ReAct agent loop with tool calling support."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        call_llm_func: Callable,
        system_prompt: str,
        max_iterations: int = 10,
    ):
        self.tool_registry = tool_registry
        self.call_llm = call_llm_func
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations

    async def run(self, messages: list[dict]) -> dict:
        """Run the agent loop on a conversation.

        Args:
            messages: List of messages in OpenAI format, e.g.
                [{"role": "user", "content": "上月销量多少？"}]

        Returns:
            dict with "role": "assistant" and "content": str
        """
        iteration = 0
        conversation = list(messages)

        while iteration < self.max_iterations:
            iteration += 1
            start_time = time.time()

            # --- Step 1: Call LLM ---
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    *conversation,
                ],
                tools=self.tool_registry.to_openai_tools(),
                tool_choice="auto",
            )

            response_message = response.choices[0].message

            # --- Step 2: Check if LLM wants to call a tool ---
            if not response_message.tool_calls:
                # No tool calls — this is the final answer
                return {
                    "role": "assistant",
                    "content": response_message.content or "",
                    "tool_calls": [],
                }

            # --- Step 3: Execute tool calls ---
            conversation.append({
                "role": "assistant",
                "content": response_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in response_message.tool_calls
                ],
            })

            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                # Execute the tool
                result = await self.tool_registry.call_tool(tool_name, arguments)

                # Add tool result to conversation
                conversation.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            elapsed = time.time() - start_time

        # Max iterations reached — return last assistant message or summary
        return {
            "role": "assistant",
            "content": "抱歉，处理太久了，请简化一下问题再试。",
        }

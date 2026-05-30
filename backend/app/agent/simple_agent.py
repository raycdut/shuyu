"""ReAct Agent Loop — self-built, no framework.

The agent:
1. Receives a user message
2. Decides whether to call a tool or respond directly
3. If calling a tool: executes it, observes the result, repeats from 2
4. If responding: formats and returns the answer
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

from .tools.registry import ToolRegistry

logger = logging.getLogger("shuyu.agent")


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
        """Run the agent loop on a conversation."""
        iteration = 0
        conversation = list(messages)
        logger.info("Agent loop started")

        while iteration < self.max_iterations:
            iteration += 1
            start_time = time.time()

            # --- Step 1: Call LLM ---
            tools_def = self.tool_registry.to_openai_tools()
            logger.info(f"Agent LLM call iter {iteration}: {len(conversation)} msgs, {len(tools_def)} tools")
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    *conversation,
                ],
                tools=self.tool_registry.to_openai_tools() if tools_def else None,
            )

            response_message = response.choices[0].message

            # --- Step 2: Check if LLM wants to call a tool ---
            if not response_message.tool_calls:
                logger.info(f"Agent loop: final answer ({len(response_message.content or '')} chars)")
                result = {
                    "role": "assistant",
                    "content": response_message.content or "",
                    "tool_calls": [],
                }
                # Preserve DeepSeek reasoning_content
                rc = getattr(response_message, "reasoning_content", None)
                if rc:
                    result["reasoning_content"] = rc
                return result

            logger.info(f"Agent loop iter {iteration}: LLM requested {len(response_message.tool_calls)} tool call(s)")

            # --- Step 3: Execute tool calls ---
            assistant_msg = {
                "role": "assistant",
                "content": response_message.content or "Let me check the database...",
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
            }

            # Preserve DeepSeek reasoning_content
            rc = getattr(response_message, "reasoning_content", None)
            if rc:
                assistant_msg["reasoning_content"] = rc

            conversation.append(assistant_msg)

            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                # Execute the tool
                logger.info(f"  -> Calling tool: {tool_name}({json.dumps(arguments, ensure_ascii=False)[:100]})")
                result = await self.tool_registry.call_tool(tool_name, arguments)
                logger.info(f"  <- Tool result: {len(result)} chars")

                # Add tool result to conversation
                conversation.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            elapsed = time.time() - start_time

        # Max iterations reached — build summary of what was done
        tool_summary = []
        for msg in conversation:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    try:
                        args = json.loads(tc["function"]["arguments"])
                        q = args.get("question", "")[:60]
                        tool_summary.append(q)
                    except Exception:
                        pass
        summary = "\n".join(f"  · {q}" for q in tool_summary[:5])
        remaining = len(tool_summary) - 5
        if remaining > 0:
            summary += f"\n  · ...还有 {remaining} 次查询"

        msg = f"抱歉，处理时间过长，无法完成。\n\n已执行的查询：\n{summary}\n\n建议把问题拆成更小的步骤再问。"
        return {
            "role": "assistant",
            "content": msg,
        }

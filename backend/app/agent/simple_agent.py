"""ReAct Agent Loop — self-built, no framework.

The agent:
1. Receives a user message
2. Decides whether to call a tool or respond directly
3. If calling a tool: executes it (parallel), observes the result, repeats from 2
4. If responding: formats and returns the answer
5. Loop detection: prevents repeated similar tool calls
6. Context compression: summarizes old conversation after 3 iterations
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable

from .tools.registry import ToolRegistry

logger = logging.getLogger("shuyu.agent")


class SimpleAgent:
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
        self._tool_history: list[tuple[str, dict]] = []

    # ------------------------------------------------------------------
    # Normalize LLM response (provider-agnostic)
    # ------------------------------------------------------------------

    def _normalize(self, raw_response) -> dict:
        """Convert any provider's response to a standard dict."""
        if hasattr(raw_response, "choices"):
            msg = raw_response.choices[0].message
            tool_calls = []
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    })
            return {
                "content": msg.content or "",
                "tool_calls": tool_calls,
                "reasoning_content": getattr(msg, "reasoning_content", None),
            }
        raise ValueError(f"Unsupported LLM response type: {type(raw_response)}")

    # ------------------------------------------------------------------
    # Loop detection — prevent repeating the same tool call
    # ------------------------------------------------------------------

    def is_stuck(self, tool_name: str, arguments: dict) -> bool:
        """Detect if the agent is calling the same tool with similar args repeatedly."""
        self._tool_history.append((tool_name, arguments))

        if len(self._tool_history) < 4:
            return False

        # Last 3 calls same tool
        last_3 = self._tool_history[-3:]
        if all(t[0] == tool_name for t in last_3):
            questions = [t[1].get("question", "") for t in last_3]
            # Check if questions are similar (all mention the same entities)
            if len(set(questions)) < 2:
                logger.warning(f"Loop detected: {tool_name} called 3x with similar questions")
                return True
        return False

    # ------------------------------------------------------------------
    # Context compression — summarize old conversation mid-loop
    # ------------------------------------------------------------------

    def _compress_history(self, conversation: list) -> list:
        """Compress older messages when conversation grows too long."""
        if len(conversation) < 8:
            return conversation

        # Find safe cut point: keep last 2 complete exchange pairs
        # (assistant+tool_calls → tool results → next round)
        exchange_count = 0
        cut_idx = len(conversation)
        for i in range(len(conversation) - 1, -1, -1):
            msg = conversation[i]
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                exchange_count += 1
                if exchange_count >= 2:
                    cut_idx = i
                    break

        if cut_idx >= len(conversation) - 2:
            return conversation

        keep = conversation[:1] + conversation[cut_idx:]
        removed = len(conversation) - len(keep)
        return keep[:1] + [
            {"role": "system", "content": f"历史上下文已压缩，已省略中间 {removed} 条消息。当前对话继续。"}
        ] + keep[1:]

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self, messages: list[dict]) -> dict:
        """Run the agent loop on a conversation."""
        iteration = 0
        conversation = list(messages)
        self._tool_history.clear()
        logger.info("Agent loop started")

        while iteration < self.max_iterations:
            iteration += 1
            start_time = time.time()

            # Compress history every 3 iterations
            if iteration > 1 and iteration % 3 == 0:
                conversation = self._compress_history(conversation)

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

            normalized = self._normalize(response)

            # --- Step 2: Check if LLM wants to call a tool ---
            if not normalized["tool_calls"]:
                logger.info(f"Agent loop: final answer ({len(normalized['content'])} chars)")
                result = {
                    "role": "assistant",
                    "content": normalized["content"],
                    "tool_calls": [],
                }
                if normalized["reasoning_content"]:
                    result["reasoning_content"] = normalized["reasoning_content"]
                return result

            logger.info(f"Agent loop iter {iteration}: LLM requested {len(normalized['tool_calls'])} tool call(s)")

            # --- Step 3: Execute tool calls (parallel) ---
            assistant_msg = {
                "role": "assistant",
                "content": normalized["content"] or "Let me check the database...",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        },
                    }
                    for tc in normalized["tool_calls"]
                ],
            }
            if normalized["reasoning_content"]:
                assistant_msg["reasoning_content"] = normalized["reasoning_content"]

            conversation.append(assistant_msg)

            # Execute all tool calls in parallel
            async def execute_one(tc: dict) -> dict:
                tool_name = tc["name"]
                try:
                    arguments = json.loads(tc["arguments"])
                except json.JSONDecodeError:
                    arguments = {}

                # Loop detection
                if self.is_stuck(tool_name, arguments):
                    return {
                        "tool_call_id": tc["id"],
                        "content": f"⚠️ 你已经在反复查询同一类数据（{tool_name}）。如果找不到结果，请直接告知用户无法获取该数据。",
                    }

                logger.info(f"  -> Calling tool: {tool_name}({json.dumps(arguments, ensure_ascii=False)[:100]})")
                try:
                    result = await self.tool_registry.call_tool(tool_name, arguments)
                    logger.info(f"  <- Tool result: {len(result)} chars")
                    return {"tool_call_id": tc["id"], "content": result}
                except Exception as e:
                    err = f"工具 {tool_name} 执行失败：{e}\n请调整参数后重试。"
                    logger.error(f"  <- Tool error: {e}")
                    return {"tool_call_id": tc["id"], "content": err}

            results = await asyncio.gather(*[execute_one(tc) for tc in normalized["tool_calls"]])
            for r in results:
                conversation.append({
                    "role": "tool",
                    "tool_call_id": r["tool_call_id"],
                    "content": r["content"],
                })

            elapsed = time.time() - start_time

        # Max iterations reached — build summary
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
        return {"role": "assistant", "content": msg}

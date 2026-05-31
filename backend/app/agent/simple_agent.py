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
        self._tool_history: list[str] = []

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

            content = msg.content or ""
            # Clean up DeepSeek tool call leaks in the content
            if "<｜｜DSML｜｜tool_calls>" in content:
                content = content.split("<｜｜DSML｜｜tool_calls>")[0].strip()

            return {
                "content": content,
                "tool_calls": tool_calls,
                "reasoning_content": getattr(msg, "reasoning_content", None),
            }
        raise ValueError(f"Unsupported LLM response type: {type(raw_response)}")

    # ------------------------------------------------------------------
    # Loop detection — prevent repeating the same tool call
    # ------------------------------------------------------------------

    def _canonicalize_json(self, obj: Any) -> Any:
        """Canonicalize JSON-like structures for stable tool-call signatures."""
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj.strip() if isinstance(obj, str) else obj
        if isinstance(obj, list):
            return [self._canonicalize_json(v) for v in obj]
        if isinstance(obj, dict):
            return {str(k): self._canonicalize_json(obj[k]) for k in sorted(obj.keys(), key=lambda x: str(x))}
        return str(obj)

    def _tool_signature(self, tool_name: str, arguments: dict) -> str:
        """Build a stable signature for a tool call."""
        canonical = self._canonicalize_json(arguments)
        return f"{tool_name}:{json.dumps(canonical, ensure_ascii=False, sort_keys=True)}"

    def is_stuck(self, tool_name: str, arguments: dict) -> bool:
        """Detect if the agent is calling the same tool with similar args repeatedly."""
        sig = self._tool_signature(tool_name, arguments)
        self._tool_history.append(sig)
        if len(self._tool_history) < 4:
            return False
        last_3 = self._tool_history[-3:]
        if all(s == sig for s in last_3):
            logger.warning(f"Loop detected: {tool_name} called 3x with same signature")
            return True
        return False

    # ------------------------------------------------------------------
    # Context compression — summarize old conversation mid-loop
    # ------------------------------------------------------------------

    async def _compress_history(self, conversation: list) -> list:
        """Compress older messages by summarizing them into a single system message."""
        if len(conversation) < 8:
            return conversation

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

        head = conversation[:1]
        mid = conversation[1:cut_idx]
        tail = conversation[cut_idx:]

        lines = []
        for m in mid:
            role = m.get("role")
            if role in ("user", "assistant", "tool"):
                c = (m.get("content") or "").strip()
                if role == "tool":
                    tcid = m.get("tool_call_id", "")
                    lines.append(f"[tool {tcid}] {c[:300]}")
                else:
                    lines.append(f"[{role}] {c[:300]}")
        payload = "\n".join(lines)[:6000]

        response = await self.call_llm(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是对话压缩器。请把下面的对话压缩成一段简洁摘要，保留：用户目标、关键约束、"
                        "已执行的查询/工具调用要点、关键结论、仍未解决的问题。不要编造。输出纯文本摘要。"
                    ),
                },
                {"role": "user", "content": payload},
            ],
            tools=None,
        )
        summary = self._normalize(response).get("content", "").strip()
        summary_msg = {"role": "system", "content": f"对话摘要（压缩版）：{summary}" if summary else "对话摘要（压缩版）：(empty)"}
        return head + [summary_msg] + tail

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
                conversation = await self._compress_history(conversation)

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
                "content": normalized["content"] or "我来查一下数据库…",
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

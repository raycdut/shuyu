"""Advanced Agent — Plan → ReAct → Reflect.

Quality mode for complex analysis:
1. Plan: LLM creates an analysis plan (no tools)
2. ReAct: Executes the plan step by step (tools available)
3. Reflect: Reviews results and produces final summary (no tools)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from .tools.registry import ToolRegistry

logger = logging.getLogger("shuyu.agent")

PLAN_PROMPT = """你是数据分析规划师。根据用户的问题和数据库结构，制定详细的分析计划。

## 严格规则
- 不要查询数据，只制定计划
- 不要写 SQL，只写分析思路
- 必须按下面的格式输出，不要自己发挥

## 输出格式（必须严格遵守）

## 分析目标
[一句话说明用户想分析什么]

## 分析步骤
1. **第一步**：[分析思路，比如：按客户 group by 汇总订单数量，找出购买商品最多的客户] — [原因]
2. **第二步**：[分析思路，比如：用上一步的客户ID去查订单明细表，获取购买的产品名称和数量] — [原因]
3. **第三步**：[分析思路] — [原因]
...
"""

REFLECT_PROMPT = """回顾刚才的分析过程和结果：
1. 所有查询是否成功执行？
2. 结果是否能回答用户的问题？
3. 有没有什么有趣的发现或异常？

如果已经充分回答了用户的问题，输出汇总报告。
如果缺少关键信息，请告知用户。"""


class AdvancedAgent:
    """Plan → ReAct → Reflect agent for complex analysis."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        call_llm_func: Callable,
        system_prompt: str,
        max_iterations: int = 15,
    ):
        self.tool_registry = tool_registry
        self.call_llm = call_llm_func
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations

    async def run(self, messages: list[dict], progress_callback: Callable | None = None) -> dict:
        """Run the full Plan → ReAct → Reflect pipeline."""
        conversation = list(messages)

        # ============ Phase 1: Plan (no tools) ============
        logger.info("AdvancedAgent: Phase 1 — Plan")
        plan_response = await self.call_llm(
            messages=[
                {"role": "system", "content": PLAN_PROMPT + "\n\n" + self.system_prompt},
                *conversation,
            ],
            tools=None,  # no tools during planning
        )
        plan_text = self._extract_content(plan_response)
        logger.info(f"AdvancedAgent: Plan generated ({len(plan_text)} chars)")
        if progress_callback:
            await progress_callback({"type": "plan", "content": plan_text, "collapsible": True})

        # Add plan to conversation as context
        conversation.append({"role": "assistant", "content": plan_text})

        # ============ Phase 2: ReAct (with tools) ============
        logger.info("AdvancedAgent: Phase 2 — ReAct")
        if progress_callback:
            await progress_callback({"type": "react", "content": "🔍 正在按计划执行查询..."})
        exec_prompt = f"你正在执行以下分析计划：\n{plan_text}\n\n按计划步骤依次执行，每步调用 query_database 工具查询，完成后输出阶段性发现。"
        tools_def = self.tool_registry.to_openai_tools()

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1

            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": exec_prompt},
                    *conversation,
                ],
                tools=tools_def,
            )

            normalized = self._normalize(response)

            if not normalized["tool_calls"]:
                logger.info(f"AdvancedAgent: ReAct iteration {iteration} — final answer")
                conversation.append({"role": "assistant", "content": normalized["content"]})
                break

            # Exit loop if we already have enough data (>200 chars) and LLM is still probing
            if iteration > 1:
                tool_count = sum(1 for m in conversation if m.get("role") == "tool" and len(m.get("content","")) > 200)
                if tool_count >= 2 and len(normalized["tool_calls"]) > 0:
                    # Check if the LLM is asking about a table/column schema (probing)
                    questions = [tc.get("arguments","") for tc in normalized["tool_calls"]]
                    probing = any("字段" in q or "列名" in q or "column" in q.lower() or "describe" in q.lower() for q in questions)
                    if probing:
                        logger.warning(f"AdvancedAgent: Data already retrieved, breaking probing loop")
                        break

            logger.info(f"AdvancedAgent: ReAct iteration {iteration} — {len(normalized['tool_calls'])} tool call(s)")

            # Execute tools (parallel)
            from .simple_agent import SimpleAgent

            assistant_msg = {
                "role": "assistant",
                "content": normalized["content"] or "Let me check the database...",
                "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in normalized["tool_calls"]
                ],
            }
            conversation.append(assistant_msg)

            async def execute_one(tc: dict) -> dict:
                tool_name = tc["name"]
                try:
                    args = json.loads(tc["arguments"])
                except json.JSONDecodeError:
                    args = {}
                try:
                    result = await self.tool_registry.call_tool(tool_name, args)
                    logger.info(f"  <- Tool result: {len(result)} chars")
                    if progress_callback:
                        q = json.dumps(args, ensure_ascii=False)[:80]
                        await progress_callback({"type": "query", "content": f"📊 查询完成: {q}"})
                    return {"tool_call_id": tc["id"], "content": result}
                except Exception as e:
                    return {"tool_call_id": tc["id"], "content": f"工具执行失败：{e}"}

            import asyncio
            results = await asyncio.gather(*[execute_one(tc) for tc in normalized["tool_calls"]])
            for r in results:
                conversation.append({"role": "tool", "tool_call_id": r["tool_call_id"], "content": r["content"]})

        # ============ Phase 3: Reflect (no tools) — only if needed ============
        # If ReAct already produced a good answer, skip Reflect
        final_react = None
        for msg in reversed(conversation):
            if msg.get("role") == "assistant" and not msg.get("tool_calls"):
                final_react = msg["content"]
                break

        if final_react and len(final_react) > 200:
            logger.info(f"AdvancedAgent: Skipping Reflect (ReAct answer is sufficient: {len(final_react)} chars)")
            final = final_react
        else:
            logger.info("AdvancedAgent: Phase 3 — Reflect")
            if progress_callback:
                await progress_callback({"type": "summarize", "content": "📝 正在汇总分析结果..."})
            reflect_response = await self.call_llm(
                messages=[
                    {"role": "system", "content": REFLECT_PROMPT},
                    *conversation,
                ],
                tools=None,
            )
            final = self._extract_content(reflect_response)
            logger.info(f"AdvancedAgent: Reflect complete ({len(final)} chars)")

        if progress_callback:
            await progress_callback({"type": "done", "content": final})

        return {"role": "assistant", "content": final, "tool_calls": []}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _normalize(self, raw_response) -> dict:
        """Standardize LLM response."""
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
        raise ValueError(f"Unsupported response type: {type(raw_response)}")

    def _extract_content(self, response: Any) -> str:
        """Extract text content from LLM response."""
        return self._normalize(response)["content"]

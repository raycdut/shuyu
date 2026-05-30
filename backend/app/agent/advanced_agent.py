"""Advanced Agent — Plan → ReAct → Reflect.

Quality mode for complex analysis:
1. Plan: LLM creates an analysis plan (no tools)
2. ReAct: Executes the plan step by step (tools available)
3. Reflect: Reviews results and produces final summary (no tools)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

from .. import state
from .tools.registry import ToolRegistry

logger = logging.getLogger("shuyu.agent")

PLAN_PROMPT = """你是数据分析规划师。根据用户的问题和数据库结构，制定分析计划。

## 严格规则
- 不要查询数据，只制定计划
- **每步必须写出具体 SQL 思路**，包括表名、关联字段、聚合方式
- **如果一条 SQL 能解决问题，不要拆成多步**
- 必须按下面的格式输出

## 输出格式

## 分析目标
[一句话说明]

## 分析步骤
1. **第一步**：[SQL 思路：FROM 哪个表 JOIN 哪个表，用什么字段 GROUP BY/ORDER BY] — [原因]
2. **第二步**：[可选，只有确实需要多步时才写]
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
        self._tool_history: list[tuple[str, dict]] = []
        self._sql_queries: list[str] = []

    def _is_stuck(self, tool_name: str, arguments: dict) -> bool:
        """Detect if the agent is calling the same tool with similar args repeatedly.

        Ported from SimpleAgent.is_stuck to provide loop detection in ReAct phase.
        """
        self._tool_history.append((tool_name, arguments))

        if len(self._tool_history) < 4:
            return False

        last_3 = self._tool_history[-3:]
        if all(t[0] == tool_name for t in last_3):
            questions = [t[1].get("question", "") for t in last_3]
            if len(set(questions)) < 2:
                logger.warning(f"AdvancedAgent: Loop detected — {tool_name} called 3x with similar questions")
                return True
        return False

    async def run(self, messages: list[dict], progress_callback: Callable | None = None) -> dict:
        """Run the full Plan → ReAct → Reflect pipeline."""
        conversation = list(messages)
        self._tool_history.clear()
        self._sql_queries.clear()

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
        exec_prompt = f"你正在执行以下分析计划：\n{plan_text}\n\n按计划步骤依次执行，每步调用 query_database 工具查询，完成后输出阶段性发现。\n注意：不要重复查询已经获取过的数据。"
        tools_def = self.tool_registry.to_openai_tools()

        iteration = 0
        tool_data_accumulated = 0  # total bytes of meaningful tool result data

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

            # Loop detection: if is_stuck returns True, break the ReAct loop
            # and let Reflect phase handle the incomplete answer
            tool_looping = False
            for tc in normalized["tool_calls"]:
                try:
                    args = json.loads(tc.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                if self._is_stuck(tc["name"], args):
                    tool_looping = True
                    break
            if tool_looping:
                logger.warning(f"AdvancedAgent: Loop detected at iteration {iteration}, breaking to Reflect")
                conversation.append({
                    "role": "assistant",
                    "content": "已获取了足够的数据，准备汇总分析结果。"
                })
                break

            # Exit loop if probing individual entities (territory/customer one at a time)

            # Detect schema probing loop: if LLM keeps inspecting columns after getting data
            if iteration > 4:
                tool_msgs = [m for m in conversation if m.get("role") == "tool"]
                has_data = any(len(m.get("content", "")) > 300 for m in tool_msgs)
                if has_data:
                    # Check if newest tool calls are schema questions
                    questions = []
                    for tc in normalized.get("tool_calls", []):
                        try:
                            q = json.loads(tc.get("arguments", "{}")).get("question", "")
                            questions.append(q)
                        except Exception:
                            pass
                    if questions and all("字段" in q or "列名" in q or "column" in q.lower() or "describe" in q.lower() for q in questions):
                        logger.warning(f"AdvancedAgent: Already have data, breaking schema-probing loop")
                        conversation.append({"role": "system", "content": "你已经收集了足够的数据，请根据已有查询结果直接回答用户的问题。"})
                        break

            logger.info(f"AdvancedAgent: ReAct iteration {iteration} — {len(normalized['tool_calls'])} tool call(s)")

            # Execute tools (parallel)
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

            results = await asyncio.gather(*[execute_one(tc) for tc in normalized["tool_calls"]])
            for r in results:
                conversation.append({"role": "tool", "tool_call_id": r["tool_call_id"], "content": r["content"]})
                tool_data_accumulated += len(r["content"])

        # ============ Phase 3: Reflect ============
        # Skip Reflect if ReAct produced a non-plan final answer
        # Find the latest ReAct final answer (skip plan messages)
        final_react = None
        for msg in reversed(conversation):
            if (msg.get("role") == "assistant" and not msg.get("tool_calls")
                    and not msg.get("content", "").startswith("## 分析")):
                final_react = msg["content"]
                break

        has_data = tool_data_accumulated > 0
        has_plan_text = len(plan_text) > 50

        # Skip Reflect only when: ReAct produced a meaningful answer, data was collected,
        # and the answer mentions concrete numbers/results (not just a loop break message)
        if final_react and has_data and len(final_react) > 50 and "已获取了足够的数据" not in final_react:
            logger.info(
                f"AdvancedAgent: Skipping Reflect "
                f"(ReAct answer: {len(final_react)} chars, data: {tool_data_accumulated} bytes)"
            )
            final = final_react
        else:
            logger.info(
                f"AdvancedAgent: Phase 3 — Reflect "
                f"(final_react={len(final_react) if final_react else 0} chars, "
                f"data={tool_data_accumulated} bytes)"
            )
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
            await progress_callback({"type": "done", "content": final, "sql_queries": state._last_sql_queries})

        return {
            "role": "assistant",
            "content": final,
            "tool_calls": [],
            "sql_queries": self._sql_queries,
        }

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

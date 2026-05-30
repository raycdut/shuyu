"""Advanced Agent — Plan → Reflect → Execute → Report → Reflect.

Quality mode for complex analysis:
1. Plan: LLM creates an analysis plan (no tools)
2. Reflect on Plan: Review plan for correctness, feasibility; iterate if needed
3. Execute: Step-by-step execution with per-step result validation
4. Report: Generate final report from collected data
5. Reflect on Report: Review report quality, supplement if needed
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Callable

from .tools.registry import ToolRegistry

logger = logging.getLogger("shuyu.agent")

PLAN_PROMPT = """你是数据分析规划师。根据用户的提问和下方数据库结构，制定分析计划。

## 可用数据库
<database_schema>
请在下方 `<database>` 标签中查找可用的表和字段。
</database_schema>

## 严格规则
- 只使用上方 `<database>` 中列出的表和字段，不要编造不存在的表或字段
- 输出完整的、可直接执行的 SQL，写在 ```sql 代码块中
- 如果一条 SQL 能解决问题，只写一步；确实需要多步时才拆分
- 如果表结构不足以回答问题，输出「缺少必要数据：xxx」
- 不要调用工具，只写计划

## 输出格式（必须严格遵循）

## 分析目标
[一句话说明用户想分析什么]

## 分析步骤
1. **第 1 步**
   - 目的：[为什么查这个]
   - SQL：
   ```sql
   你的完整 SQL，可直接执行
   ```
2. **第 2 步**（可选）
   - 目的：
   - SQL：
   ```sql
   ...
   ```
"""

PLAN_REFLECT_PROMPT = """你是数据分析规划审核专家。请检查下面的分析计划是否合理。

检查清单：
1. 分析目标是否准确反映了用户的问题？
2. 每个分析步骤的 SQL 思路是否可行？（表名、关联字段、聚合方式是否合理）
3. 步骤顺序是否正确？（后面的步骤是否依赖前面的结果？）
4. 有没有多余的步骤？（一条 SQL 能解决的问题，不应该拆成多步）
5. 有没有遗漏重要的分析维度？

请输出：

## 审核结论
[合理 / 需要修改]

## 问题列表
- [如果有问题，逐条列出]

## 修改建议
- [如果有问题，给出具体的修改建议]

如果审核结论是「合理」，则直接输出「审核结论：合理」即可。"""

REPORT_REFLECT_PROMPT = """你是数据分析报告审核专家。请检查下面的分析报告。

检查清单：
1. 报告是否直接回应了用户的原始问题？
2. 报告中的数据是否有具体的数值支持（不应该是模糊描述）？
3. 有没有明显的遗漏或错误？
4. 是否有有趣的发现值得提及？

## 审核结论
[通过 / 需要补充]

## 问题
- [如果有问题，逐条列出]

## 需要补充的查询
- [如果需要额外数据才能完善报告，写出具体的查询思路]

如果审核通过，直接输出「审核结论：通过」即可。"""


class AdvancedAgent:
    """Plan → Reflect → Execute → Report → Reflect agent for complex analysis."""

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

    # ------------------------------------------------------------------
    # Loop detection
    # ------------------------------------------------------------------

    def _is_stuck(self, tool_name: str, arguments: dict) -> bool:
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

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    async def run(self, messages: list[dict], progress_callback: Callable | None = None) -> dict:
        """Run the full Plan → Reflect → Execute → Report → Reflect pipeline."""
        conversation = list(messages)
        self._tool_history.clear()
        self._sql_queries.clear()

        # ============ Phase 1: Plan generation ============
        plan_text = await self._phase_plan(conversation, progress_callback)

        # ============ Phase 1.5: Plan reflection (iterate if needed) ============
        plan_text = await self._phase_plan_reflect(plan_text, conversation, progress_callback)

        # ============ Phase 2: Step-by-step execution ============
        # Extract steps from the plan for granular progress tracking
        steps = self._parse_plan_steps(plan_text)
        all_data_ok = await self._phase_execute(plan_text, steps, conversation, progress_callback)

        # ============ Phase 3: Report generation ============
        final = await self._phase_report(conversation, progress_callback)

        # ============ Phase 4: Report reflection (iterate if needed) ============
        final = await self._phase_report_reflect(final, conversation, progress_callback)

        if progress_callback:
            await progress_callback({"type": "done", "content": final})

        return {
            "role": "assistant",
            "content": final,
            "tool_calls": [],
            "sql_queries": self._sql_queries,
        }

    # ------------------------------------------------------------------
    # Phase 1: Plan
    # ------------------------------------------------------------------

    async def _phase_plan(self, conversation: list, progress_callback: Callable | None) -> str:
        logger.info("AdvancedAgent: Phase 1 — Plan")
        response = await self.call_llm(
            messages=[
                {"role": "system", "content": PLAN_PROMPT + "\n\n" + self.system_prompt},
                *conversation,
            ],
            tools=None,
        )
        plan_text = self._extract_content(response)
        logger.info(f"AdvancedAgent: Plan generated ({len(plan_text)} chars)")
        logger.info(f"AdvancedAgent: Plan text preview:\n{plan_text[:500]}")
        return plan_text

    # ------------------------------------------------------------------
    # Phase 1.5: Plan reflection
    # ------------------------------------------------------------------

    async def _phase_plan_reflect(
        self, plan_text: str, conversation: list, progress_callback: Callable | None
    ) -> str:
        """Reflect on the plan, iterate up to 3 times if issues found."""
        max_rounds = 3
        current_plan = plan_text

        for round_num in range(max_rounds):
            logger.info(f"AdvancedAgent: Phase 1.5 — Plan reflect (round {round_num + 1})")

            reflect_response = await self.call_llm(
                messages=[
                    {"role": "system", "content": PLAN_REFLECT_PROMPT},
                    {"role": "assistant", "content": f"## 分析计划\n{current_plan}"},
                ],
                tools=None,
            )
            reflect_text = self._extract_content(reflect_response)
            logger.info(f"AdvancedAgent: Plan reflect input:\n{current_plan[:300]}")
            logger.info(f"AdvancedAgent: Plan reflect result ({len(reflect_text)} chars)")
            logger.info(f"AdvancedAgent: Plan reflect verdict:\n{reflect_text[:300]}")

            # Check if plan is approved
            if "审核结论" in reflect_text and "合理" in reflect_text:
                # Check for explicit "需要修改" — if both appear, "需要修改" wins
                if "需要修改" not in reflect_text.split("审核结论")[-1][:50]:
                    logger.info("AdvancedAgent: Plan approved after reflection")
                    if progress_callback:
                        await progress_callback({
                            "type": "plan_reflect",
                            "content": "✅ 计划审核通过",
                            "collapsible": True,
                        })
                    break

            # Plan needs revision — regenerate with feedback
            logger.info(f"AdvancedAgent: Plan needs revision (round {round_num + 1})")
            if progress_callback:
                await progress_callback({
                    "type": "plan_reflect",
                    "content": f"🔄 计划需要修改（第 {round_num + 1} 轮）",
                    "collapsible": True,
                })

            if round_num < max_rounds - 1:
                # Regenerate plan with reflection feedback
                response = await self.call_llm(
                    messages=[
                        {"role": "system", "content": PLAN_PROMPT + "\n\n" + self.system_prompt},
                        *conversation,
                        {"role": "assistant", "content": current_plan},
                        {"role": "user", "content": f"请根据以下审核意见修改分析计划：\n{reflect_text}"},
                    ],
                    tools=None,
                )
                current_plan = self._extract_content(response)
                logger.info(f"AdvancedAgent: Plan revised ({len(current_plan)} chars)")

        # Show final plan to frontend
        if progress_callback:
            await progress_callback({"type": "plan", "content": current_plan, "collapsible": True})

        conversation.append({"role": "assistant", "content": current_plan})
        return current_plan

    # ------------------------------------------------------------------
    # Phase 2: Step-by-step execution
    # ------------------------------------------------------------------

    def _parse_plan_steps(self, plan_text: str) -> list[dict]:
        """Extract steps + SQL from the plan.

        Returns list of dicts: [{"purpose": str, "sql": str | None}]
        """
        steps = []
        current_purpose = None
        in_code_block = False
        code_buffer = []

        for line in plan_text.split("\n"):
            # Detect ```sql or ``` code block start/end
            if line.strip().startswith("```"):
                if in_code_block:
                    # End of code block
                    sql = "\n".join(code_buffer).strip()
                    if current_purpose is not None and sql:
                        steps.append({"purpose": current_purpose, "sql": sql})
                    elif sql:
                        # SQL without a preceding purpose line — still capture it
                        steps.append({"purpose": sql[:80], "sql": sql})
                    code_buffer = []
                    in_code_block = False
                else:
                    in_code_block = True
                    code_buffer = []
                continue

            if in_code_block:
                code_buffer.append(line)
                continue

            # Match step header like "1. **第 1 步**" or "1. **Step 1**"
            step_match = re.match(r"^\s*\d+\.\s+\*{1,2}.+?\*{1,2}\s*", line)
            if step_match:
                current_purpose = line[step_match.end():].strip()
                # Remove leading dash or colon
                current_purpose = re.sub(r"^[:：\s-]+\s*", "", current_purpose)
                # Check if the rest of the line has purpose text
                if not current_purpose:
                    current_purpose = f"Step {len(steps) + 1}"
                continue

            # Detect "- 目的：xxx" lines
            purpose_match = re.match(r"^\s*-\s*目的[:：]?\s*(.*)", line)
            if purpose_match and purpose_match.group(1).strip():
                current_purpose = purpose_match.group(1).strip()
                continue

        # If the plan has no code blocks, fall back to the old text-based extraction
        if not steps:
            in_steps = False
            for line in plan_text.split("\n"):
                step_match = re.match(r"^\s*\d+\.\s+\*{1,2}.+?\*{1,2}\s*[:：]?\s*(.*)", line)
                if step_match:
                    in_steps = True
                    steps.append({"purpose": step_match.group(1).strip(), "sql": None})
                elif in_steps and line.strip() and not line.strip().startswith("#"):
                    if steps and not line.strip().startswith("-"):
                        steps[-1]["purpose"] += " " + line.strip()

        return steps

    async def _phase_execute(
        self,
        plan_text: str,
        steps: list[str],
        conversation: list,
        progress_callback: Callable | None,
    ) -> bool:
        """Execute plan steps one by one with per-step result validation."""
        logger.info(f"AdvancedAgent: Phase 2 — Execute ({len(steps)} steps)")

        if not steps:
            # Fallback: use the full plan as context for the old ReAct loop
            return await self._execute_freeform(plan_text, conversation, progress_callback)

        all_ok = True
        completed = 0

        for step_idx, step in enumerate(steps):
            step_num = step_idx + 1
            purpose = step.get("purpose", "")
            sql = step.get("sql")
            display = sql[:80] + "..." if sql else purpose[:80]
            logger.info(f"AdvancedAgent: Executing step {step_num}/{len(steps)}: {display}")

            if progress_callback:
                step_desc = purpose if purpose else (sql[:100] if sql else "")
                await progress_callback({
                    "type": "step",
                    "content": f"📋 第 {step_num}/{len(steps)} 步: {step_desc}",
                    "step": step_num,
                    "total": len(steps),
                })

            if sql:
                # Plan already has SQL — inject it directly
                step_prompt = (
                    f"你正在执行分析计划的第 {step_num} 步。\n"
                    f"目的：{purpose}\n\n"
                    f"计划的 SQL（请直接使用，不要修改）：\n"
                    f"```sql\n{sql}\n```\n\n"
                    f"调用 query_database 工具执行上述 SQL，完成后输出这一步的发现。"
                )
            else:
                step_prompt = (
                    f"你正在执行分析计划的第 {step_num} 步。\n"
                    f"当前步骤：{purpose}\n\n"
                    f"完整计划：\n{plan_text}\n\n"
                    f"执行这一步，调用 query_database 工具查询。"
                    f"完成后输出这一步的阶段性发现。"
                )

            step_ok = await self._execute_step(step_prompt, conversation, progress_callback)

            if step_ok:
                completed += 1
                if progress_callback:
                    await progress_callback({
                        "type": "step_done",
                        "content": f"✅ 第 {step_num} 步完成",
                        "step": step_num,
                    })
            else:
                all_ok = False
                if progress_callback:
                    await progress_callback({
                        "type": "step_done",
                        "content": f"⚠️ 第 {step_num} 步执行异常，已跳过",
                        "step": step_num,
                    })

        logger.info(f"AdvancedAgent: Execution complete ({completed}/{len(steps)} steps OK)")
        return all_ok

    async def _execute_step(
        self,
        step_prompt: str,
        conversation: list,
        progress_callback: Callable | None,
    ) -> bool:
        """Execute a single plan step with result validation."""
        tools_def = self.tool_registry.to_openai_tools()
        max_attempts = 2
        step_conversation = list(conversation)

        for attempt in range(max_attempts):
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": step_prompt},
                    *step_conversation,
                ],
                tools=tools_def,
            )

            normalized = self._normalize(response)

            if not normalized["tool_calls"]:
                # LLM decided to answer directly — likely a summary, accept it
                conversation.append({"role": "assistant", "content": normalized["content"]})
                # If content is substantial, consider it successful
                return len(normalized.get("content", "")) > 30

            # Execute tool calls
            assistant_msg = {
                "role": "assistant",
                "content": normalized["content"] or "Executing step...",
                "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in normalized["tool_calls"]
                ],
            }
            step_conversation.append(assistant_msg)

            results = await asyncio.gather(*[
                self._execute_tool(tc, progress_callback) for tc in normalized["tool_calls"]
            ])

            for r in results:
                step_conversation.append({
                    "role": "tool",
                    "tool_call_id": r["tool_call_id"],
                    "content": r["content"],
                })

            # Validate result quality
            has_data = any(len(r.get("content", "")) > 50 for r in results)
            has_error = any("执行失败" in r.get("content", "") or "错误" in r.get("content", "") for r in results)
            logger.info(f"AdvancedAgent: Step attempt {attempt + 1} — has_data={has_data}, has_error={has_error}, tool_results=[{', '.join(f'{len(r.get("content",""))}ch' for r in results)}]")

            if has_data and not has_error:
                # Step executed successfully
                # Merge step conversation into main conversation
                conversation.extend(step_conversation[len(conversation):])
                return True

            if has_error and attempt < max_attempts - 1:
                logger.warning(f"AdvancedAgent: Step failed, retrying (attempt {attempt + 1})")
                step_conversation.append({
                    "role": "user",
                    "content": "上一步查询失败了，请换一种查询方式重试，或者直接告知用户无法获取该数据。",
                })
                continue

            # Failed after max attempts — still merge what we have
            conversation.extend(step_conversation[len(conversation):])
            return False

        return False

    async def _execute_freeform(
        self,
        plan_text: str,
        conversation: list,
        progress_callback: Callable | None,
    ) -> bool:
        """Fallback: original free-form ReAct loop when steps can't be parsed."""
        exec_prompt = (
            f"你正在执行以下分析计划：\n{plan_text}\n\n"
            f"按计划步骤依次执行，每步调用 query_database 工具查询，完成后输出阶段性发现。\n"
            f"注意：不要重复查询已经获取过的数据。"
        )
        tools_def = self.tool_registry.to_openai_tools()

        for iteration in range(1, self.max_iterations + 1):
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": exec_prompt},
                    *conversation,
                ],
                tools=tools_def,
            )

            normalized = self._normalize(response)

            if not normalized["tool_calls"]:
                conversation.append({"role": "assistant", "content": normalized["content"]})
                return True

            # Loop detection
            loop_detected = False
            for tc in normalized["tool_calls"]:
                try:
                    args = json.loads(tc.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                if self._is_stuck(tc["name"], args):
                    loop_detected = True
                    break
            if loop_detected:
                conversation.append({"role": "assistant", "content": "已获取了足够的数据。"})
                break

            assistant_msg = {
                "role": "assistant",
                "content": normalized["content"] or "Executing...",
                "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in normalized["tool_calls"]
                ],
            }
            conversation.append(assistant_msg)

            results = await asyncio.gather(*[
                self._execute_tool(tc, progress_callback) for tc in normalized["tool_calls"]
            ])

            for r in results:
                conversation.append({
                    "role": "tool",
                    "tool_call_id": r["tool_call_id"],
                    "content": r["content"],
                })

        return True  # Best effort

    # ------------------------------------------------------------------
    # Phase 3: Report
    # ------------------------------------------------------------------

    async def _phase_report(self, conversation: list, progress_callback: Callable | None) -> str:
        """Generate final report from collected data."""
        logger.info("AdvancedAgent: Phase 3 — Report")

        if progress_callback:
            await progress_callback({"type": "summarize", "content": "📝 正在生成分析报告..."})

        response = await self.call_llm(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是数据分析报告撰写专家。根据已有查询结果，生成一份完整的分析报告。\n\n"
                        "要求：\n"
                        "1. 直接回答用户的原始问题\n"
                        "2. 使用具体的数据和数值（不要模糊描述）\n"
                        "3. 结构清晰，使用表格展示数据\n"
                        "4. 包含关键发现和结论"
                    ),
                },
                *conversation,
            ],
            tools=None,
        )
        report = self._extract_content(response)
        logger.info(f"AdvancedAgent: Report generated ({len(report)} chars)")
        logger.info(f"AdvancedAgent: Report preview:\n{report[:300]}")
        return report

    # ------------------------------------------------------------------
    # Phase 4: Report reflection
    # ------------------------------------------------------------------

    async def _phase_report_reflect(
        self,
        report: str,
        conversation: list,
        progress_callback: Callable | None,
    ) -> str:
        """Reflect on the report, iterate up to 2 times if issues found."""
        current_report = report

        for round_num in range(2):
            logger.info(f"AdvancedAgent: Phase 4 — Report reflect (round {round_num + 1})")

            reflect_response = await self.call_llm(
                messages=[
                    {"role": "system", "content": REPORT_REFLECT_PROMPT},
                    {"role": "assistant", "content": current_report},
                    *[m for m in conversation if m["role"] in ("user",)][-1:],  # Last user query
                ],
                tools=None,
            )
            reflect_text = self._extract_content(reflect_response)
            logger.info(f"AdvancedAgent: Report reflect result ({len(reflect_text)} chars)")

            # Check if report is approved
            if "审核结论" in reflect_text and "通过" in reflect_text:
                if "需要补充" not in reflect_text.split("审核结论")[-1][:50]:
                    logger.info("AdvancedAgent: Report approved after reflection")
                    if progress_callback:
                        await progress_callback({
                            "type": "report_reflect",
                            "content": "✅ 报告审核通过",
                        })
                    break

            logger.info(f"AdvancedAgent: Report needs revision (round {round_num + 1})")
            if progress_callback:
                await progress_callback({
                    "type": "report_reflect",
                    "content": "🔄 报告需要补充 ...",
                })

            # Try to supplement with additional queries
            if round_num < 1:
                issues_text = reflect_text
                supplement_response = await self.call_llm(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "根据审核意见，你需要补充查询来完善报告。\n"
                                f"审核意见：\n{issues_text}\n\n"
                                "请调用 query_database 工具执行需要的补充查询。如果不需要查询，直接输出补充后的报告。"
                            ),
                        },
                        *conversation,
                    ],
                    tools=self.tool_registry.to_openai_tools(),
                )
                supp_normalized = self._normalize(supplement_response)

                if supp_normalized["tool_calls"]:
                    # Execute supplement queries
                    supp_msg = {
                        "role": "assistant",
                        "content": supp_normalized["content"] or "补充查询中...",
                        "tool_calls": [
                            {"id": tc["id"], "type": "function",
                             "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                            for tc in supp_normalized["tool_calls"]
                        ],
                    }
                    conversation.append(supp_msg)

                    supp_results = await asyncio.gather(*[
                        self._execute_tool(tc, progress_callback) for tc in supp_normalized["tool_calls"]
                    ])
                    for r in supp_results:
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": r["tool_call_id"],
                            "content": r["content"],
                        })

                # Regenerate report with new data
                response = await self.call_llm(
                    messages=[
                        {
                            "role": "system",
                            "content": "根据所有查询结果（包括补充查询），重新生成一份完整的分析报告。",
                        },
                        *conversation,
                    ],
                    tools=None,
                )
                current_report = self._extract_content(response)
                logger.info(f"AdvancedAgent: Report regenerated ({len(current_report)} chars)")

        logger.info(f"AdvancedAgent: Report reflect final ({len(current_report)} chars)")
        logger.info(f"AdvancedAgent: Report reflect final preview:\n{current_report[:300]}")
        return current_report

    # ------------------------------------------------------------------
    # Tool execution helper
    # ------------------------------------------------------------------

    async def _execute_tool(self, tc: dict, progress_callback: Callable | None) -> dict:
        """Execute a single tool call and return the result."""
        tool_name = tc["name"]
        try:
            args = json.loads(tc.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}
        try:
            result = await self.tool_registry.call_tool(tool_name, args)
            logger.info(f"  <- Tool result: {len(result)} chars")
            if progress_callback:
                q = json.dumps(args, ensure_ascii=False)[:80]
                await progress_callback({"type": "query", "content": f"📊 查询: {q}"})
            # Track SQL queries from the global state
            from .. import state as _state
            if _state._last_sql_queries:
                self._sql_queries.extend(_state._last_sql_queries)
                _state._last_sql_queries.clear()
            return {"tool_call_id": tc["id"], "content": result}
        except Exception as e:
            err_msg = f"工具执行失败：{e}"
            logger.error(f"  <- Tool error: {e}")
            return {"tool_call_id": tc["id"], "content": err_msg}

    # ------------------------------------------------------------------
    # LLM response helpers
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

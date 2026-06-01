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

class AdvancedAgent:
    """Plan → Reflect → Execute → Report → Reflect agent for complex analysis."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        call_llm_func: Callable,
        system_prompt: str,
        plan_prompt: str,
        plan_reflect_prompt: str,
        report_reflect_prompt: str,
        max_iterations: int = 15,
    ):
        self.tool_registry = tool_registry
        self.call_llm = call_llm_func
        self.system_prompt = system_prompt
        self._plan_prompt = plan_prompt
        self._plan_reflect_prompt = plan_reflect_prompt
        self._report_reflect_prompt = report_reflect_prompt
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

        max_pipeline_retries = 2
        for pipeline_attempt in range(max_pipeline_retries):
            if pipeline_attempt > 0:
                logger.warning(f"AdvancedAgent: Starting pipeline attempt {pipeline_attempt + 1}")
                if progress_callback:
                    await progress_callback({
                        "type": "thinking",
                        "content": f"🔄 正在根据审核建议重新分析 (尝试 {pipeline_attempt + 1})...",
                    })

            # ============ Phase 1: Plan generation ============
            plan_text = await self._phase_plan(conversation, progress_callback)

            # ============ Phase 1.5: Plan reflection (iterate if needed) ============
            plan_text = await self._phase_plan_reflect(plan_text, conversation, progress_callback)

            # ============ Phase 2: Step-by-step execution ============
            # Extract steps from the plan for granular progress tracking
            steps = self._parse_plan_steps(plan_text)
            all_data_ok = await self._phase_execute(plan_text, steps, conversation, progress_callback)

            # ============ Phase 3: Report generation ============
            report = await self._phase_report(conversation, progress_callback)

            # ============ Phase 4: Report reflection (iterate if needed) ============
            final, needs_replan = await self._phase_report_reflect(report, conversation, progress_callback)
            
            if not needs_replan:
                break
            
            # If needs_replan is True, the loop continues and starts over from Phase 1
            # We might want to add some context to the conversation to tell the model why we are replanning
            conversation.append({
                "role": "system",
                "content": "之前的分析计划被审核判定为存在根本性错误。请吸取教训，重新制定更加准确的分析计划。"
            })

        try:
            from .. import state as _state

            self._sql_queries = list(_state.get_request_sql_queries())
        except Exception:
            pass
        query_results = []
        try:
            from .. import state as _state

            query_results = list(_state.get_request_query_results())
        except Exception:
            query_results = []

        if progress_callback:
            await progress_callback({
                "type": "done",
                "content": final,
                "sql_queries": self._sql_queries,
                "query_results": query_results,
            })

        return {
            "role": "assistant",
            "content": final,
            "tool_calls": [],
            "sql_queries": self._sql_queries,
            "query_results": query_results,
        }

    # ------------------------------------------------------------------
    # Phase 1: Plan
    # ------------------------------------------------------------------

    async def _phase_plan(self, conversation: list, progress_callback: Callable | None) -> str:
        logger.info("AdvancedAgent: Phase 1 — Plan")
        response = await self.call_llm(
            messages=[
                {"role": "system", "content": self._plan_prompt + "\n\n" + self.system_prompt},
                *conversation,
            ],
            tools=None,
            response_format={"type": "json_object"}
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
        """Reflect on the plan, iterate up to 3 times if issues found.

        If all rounds fail, ask the user for more information instead of
        pushing through with a weak plan.
        """
        max_rounds = 3
        current_plan = plan_text

        for round_num in range(max_rounds):
            logger.info(f"AdvancedAgent: Phase 1.5 — Plan reflect (round {round_num + 1})")

            reflect_response = await self.call_llm(
                messages=[
                    {"role": "system", "content": self._plan_reflect_prompt},
                    {"role": "assistant", "content": f"## 分析计划\n{current_plan}"},
                ],
                tools=None,
                response_format={"type": "json_object"}
            )
            reflect_text = self._extract_content(reflect_response)
            logger.info(f"AdvancedAgent: Plan reflect input:\n{current_plan[:300]}")
            logger.info(f"AdvancedAgent: Plan reflect result ({len(reflect_text)} chars)")
            logger.info(f"AdvancedAgent: Plan reflect verdict:\n{reflect_text[:300]}")

            # Check if plan is approved
            try:
                reflect_json = json.loads(reflect_text)
                if reflect_json.get("verdict") == "合理":
                    logger.info("AdvancedAgent: Plan approved after reflection")
                    if progress_callback:
                        await progress_callback({
                            "type": "plan_reflect",
                            "content": "✅ 计划审核通过",
                            "collapsible": True,
                        })
                    break
            except json.JSONDecodeError:
                pass

            # Plan needs revision — regenerate with feedback
            logger.info(f"AdvancedAgent: Plan needs revision (round {round_num + 1})")
            if progress_callback:
                await progress_callback({
                    "type": "plan_reflect",
                    "content": f"🔄 计划需要修改（第 {round_num + 1} 轮）",
                    "collapsible": True,
                })

            if round_num == max_rounds - 1:
                # All rounds failed — fall back to freeform execution with the
                # last generated plan as context, rather than asking the user
                logger.warning("AdvancedAgent: Plan failed all reflection rounds — falling back to freeform")
                # Don't break — fall through to execution with current_plan
                break

            # Regenerate plan with reflection feedback
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": self._plan_prompt + "\n\n" + self.system_prompt},
                    *conversation,
                    {"role": "assistant", "content": current_plan},
                    {"role": "user", "content": f"请根据以下审核意见修改分析计划：\n{reflect_text}"},
                ],
                tools=None,
                response_format={"type": "json_object"}
            )
            current_plan = self._extract_content(response)
            logger.info(f"AdvancedAgent: Plan revised ({len(current_plan)} chars)")

        if progress_callback:
            try:
                plan_json = json.loads(current_plan)
                display_plan = f"## 分析目标\n{plan_json.get('target', '')}\n\n## 分析步骤\n"
                for i, step in enumerate(plan_json.get("steps", [])):
                    display_plan += f"{i+1}. **目的：**{step.get('purpose', '')}\n"
                    if step.get('sql'):
                        display_plan += f"   ```sql\n   {step.get('sql')}\n   ```\n"
            except json.JSONDecodeError:
                display_plan = current_plan

            await progress_callback({"type": "plan", "content": display_plan, "collapsible": True})

        conversation.append({"role": "assistant", "content": current_plan})
        return current_plan

    # ------------------------------------------------------------------
    # Phase 2: Step-by-step execution
    # ------------------------------------------------------------------

    def _parse_plan_steps(self, plan_text: str) -> list[dict]:
        """Extract steps + SQL from the JSON plan.

        Returns list of dicts: [{"purpose": str, "sql": str | None}]
        """
        try:
            plan = json.loads(plan_text)
            steps = []
            for step in plan.get("steps", []):
                steps.append({
                    "purpose": step.get("purpose", ""),
                    "sql": step.get("sql")
                })
            return steps
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON plan, falling back to empty steps.")
            return []

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
                # Plan already has SQL — tell the model to use `sql` parameter directly
                step_prompt = (
                    f"你正在执行分析计划的第 {step_num} 步。\n"
                    f"目的：{purpose}\n\n"
                    f"计划的 SQL（请直接使用，不要修改）：\n"
                    f"```sql\n{sql}\n```\n\n"
                    f"调用 query_database(sql=...) 直接执行上述 SQL（不要用 question 参数，用 sql 参数），"
                    f"等待查询结果后输出这一步的发现。"
                )
            else:
                step_prompt = (
                    f"你正在执行分析计划的第 {step_num} 步。\n"
                    f"当前步骤：{purpose}\n\n"
                    f"完整计划：\n{plan_text}\n\n"
                    f"执行这一步，调用 query_database(question=...) 或 query_database(sql=...) 查询。"
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
            def _is_error_text(text: str) -> bool:
                return any(
                    text.strip().startswith(prefix)
                    for prefix in ("工具执行失败", "SQL 执行失败", "⚠️", "无法生成 SQL")
                )

            def _is_success_result(r: dict) -> bool:
                content = r.get("content", "")
                if _is_error_text(content):
                    return False
                if r.get("tool_name") == "query_database":
                    if "数据来源标记:[Q" not in content:
                        return False
                    if "(empty result set)" in content:
                        return False
                    return True
                return len(content.strip()) > 30

            has_data = any(_is_success_result(r) for r in results)
            has_error = any(_is_error_text(r.get("content", "")) for r in results)
            sizes = ", ".join(f"{len(r.get('content', ''))}ch" for r in results)
            logger.info(f"AdvancedAgent: Step attempt {attempt + 1} — has_data={has_data}, has_error={has_error}, tool_results=[{sizes}]")

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
            "<instructions>"
            "<task>执行分析计划</task>"
            f"<plan>{plan_text}</plan>"
            "<rules>"
            "<rule>按计划步骤依次执行，每步调用 query_database 工具查询，完成后输出阶段性发现</rule>"
            "<rule>不要重复查询已经获取过的数据</rule>"
            "</rules>"
            "</instructions>"
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

    async def _phase_report(
        self, conversation: list, progress_callback: Callable | None
    ) -> str:
        """Generate final report from collected data."""
        logger.info("AdvancedAgent: Phase 3 — Report")

        if progress_callback:
            await progress_callback({"type": "summarize", "content": "📝 正在生成分析报告..."})

        response = await self.call_llm(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "<instructions>"
                        "<role>数据分析报告撰写专家</role>"
                        "<language>zh-CN</language>"
                        "<task>根据已有查询结果，生成一份完整的分析报告</task>"
                        "<requirements>"
                        "<item>直接回答用户的原始问题</item>"
                        "<item>使用具体的数据和数值（不要模糊描述）</item>"
                        "<item>结构清晰，使用表格展示数据</item>"
                        "<item>包含关键发现和结论</item>"
                        "</requirements>"
                        "</instructions>"
                    ),
                },
                *conversation,
            ],
            tools=None,
        )
        report = self._extract_content(response)
        if not report.strip():
            logger.warning("AdvancedAgent: Report generation returned empty, falling back to conversation summary")
            # 从对话中提取最后几条消息作为兜底报告
            last_msgs = [m for m in conversation if m["role"] in ("user", "assistant")][-4:]
            report = "\n\n".join(
                m["content"][:500] for m in last_msgs if m.get("content")
            )
            if not report.strip():
                report = "分析完成，但没有生成可读的报告。请查看下方的查询结果获取数据。"
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
    ) -> tuple[str, bool]:
        """Reflect on the report, iterate up to 2 times if issues found.
        
        Returns (final_report, needs_replan)
        """
        current_report = report

        for round_num in range(2):
            logger.info(f"AdvancedAgent: Phase 4 — Report reflect (round {round_num + 1})")

            reflect_response = await self.call_llm(
                messages=[
                    {"role": "system", "content": self._report_reflect_prompt},
                    {"role": "assistant", "content": current_report},
                    *[m for m in conversation if m["role"] in ("user",)][-1:],  # Last user query
                ],
                tools=None,
                response_format={"type": "json_object"}
            )
            reflect_text = self._extract_content(reflect_response)
            logger.info(f"AdvancedAgent: Report reflect result ({len(reflect_text)} chars)")

            try:
                reflect_json = json.loads(reflect_text)
                verdict = reflect_json.get("verdict", "")
                needs_new_plan = reflect_json.get("needs_new_plan", False)

                if verdict == "通过":
                    logger.info("AdvancedAgent: Report approved after reflection")
                    if progress_callback:
                        await progress_callback({
                            "type": "report_reflect",
                            "content": "✅ 报告审核通过",
                        })
                    return current_report, False

                if needs_new_plan:
                    logger.warning("AdvancedAgent: Report reflection suggests a NEW PLAN is needed")
                    if progress_callback:
                        await progress_callback({
                            "type": "report_reflect",
                            "content": "⚠️ 发现计划存在根本性错误，准备重新制定计划...",
                        })
                    return current_report, True

            except json.JSONDecodeError:
                logger.error("Failed to parse report reflect JSON, skipping round.")
                continue

            logger.info(f"AdvancedAgent: Report needs revision (round {round_num + 1})")
            if progress_callback:
                await progress_callback({
                    "type": "report_reflect",
                    "content": f"🔄 报告需要补充 (轮次 {round_num + 1})",
                })

            # Try to supplement with additional queries
            if round_num < 1:
                issues_text = json.dumps(reflect_json.get("issues", []), ensure_ascii=False)
                suggestions_text = json.dumps(reflect_json.get("suggestions", []), ensure_ascii=False)
                
                # 记录补充前的报告内容，用于兜底
                prev_report = current_report
                supplement_response = await self.call_llm(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "<instructions>"
                                "<task>根据审核意见补充查询来完善报告</task>"
                                f"<issues>{issues_text}</issues>"
                                f"<suggestions>{suggestions_text}</suggestions>"
                                "<action>请调用 query_database 工具执行需要的补充查询。如果不需要查询，直接输出补充后的报告。</action>"
                                "</instructions>"
                            ),
                        },
                        *conversation,
                    ],
                    tools=self.tool_registry.to_openai_tools(),
                )
                supp_normalized = self._normalize(supplement_response)

                if supp_normalized["tool_calls"]:
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
                            "content": "<instructions><task>根据所有查询结果（包括补充查询），重新生成一份完整的分析报告</task></instructions>",
                        },
                        *conversation,
                    ],
                    tools=None,
                )
                regenerated = self._extract_content(response)
                # 兜底：如果重新生成的内容为空，保留补充前的报告
                if regenerated.strip():
                    current_report = regenerated
                    logger.info(f"AdvancedAgent: Report regenerated ({len(current_report)} chars)")
                else:
                    logger.warning("AdvancedAgent: Report regeneration returned empty, keeping previous report")
                    current_report = prev_report

        # Clean up DeepSeek tool call leaks in the report text
        if "<｜｜DSML｜｜tool_calls>" in current_report:
            logger.warning("DeepSeek tool call leak detected in report reflect final, stripping it.")
            current_report = current_report.split("<｜｜DSML｜｜tool_calls>")[0].strip()

        # 最终兜底：如果报告仍为空，回退到原始报告或对话摘要
        if not current_report.strip():
            logger.warning("AdvancedAgent: Final report is empty after reflection, falling back to original report or summary")
            if report.strip():
                current_report = report
            else:
                last_msgs = [m for m in conversation if m["role"] in ("user", "assistant")][-4:]
                fallback = "\n\n".join(
                    m["content"][:500] for m in last_msgs if m.get("content")
                )
                current_report = fallback or "分析完成，但没有生成可读的报告。请查看下方的查询结果获取数据。"

        logger.info(f"AdvancedAgent: Report reflect final ({len(current_report)} chars)")
        logger.info(f"AdvancedAgent: Report reflect final preview:\n{current_report[:300]}")
        return current_report, False

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
            return {"tool_call_id": tc["id"], "tool_name": tool_name, "content": result}
        except Exception as e:
            err_msg = f"工具执行失败：{e}"
            logger.error(f"  <- Tool error: {e}")
            return {"tool_call_id": tc["id"], "tool_name": tool_name, "content": err_msg}

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
            
            content = msg.content or ""
            # Clean up DeepSeek tool call leaks in the content
            if "<｜｜DSML｜｜tool_calls>" in content:
                content = content.split("<｜｜DSML｜｜tool_calls>")[0].strip()

            return {
                "content": content,
                "tool_calls": tool_calls,
                "reasoning_content": getattr(msg, "reasoning_content", None),
            }
        raise ValueError(f"Unsupported response type: {type(raw_response)}")

    def _extract_content(self, response: Any) -> str:
        """Extract text content from LLM response."""
        return self._normalize(response)["content"]

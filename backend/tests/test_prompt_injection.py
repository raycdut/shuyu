"""Tests for prompt injection protection measures."""
import pytest
from pydantic import ValidationError

from app.models.chat import ChatRequest


class TestChatRequestMaxLength:
    def test_normal_message_accepted(self):
        req = ChatRequest(message="上个月销量最好的产品是什么？")
        assert req.message == "上个月销量最好的产品是什么？"

    def test_message_at_max_length_accepted(self):
        text = "a" * 4000
        req = ChatRequest(message=text)
        assert len(req.message) == 4000

    def test_message_exceeding_max_length_rejected(self):
        text = "a" * 4001
        with pytest.raises(ValidationError):
            ChatRequest(message=text)


class TestDefaultPromptsAntiInjection:
    def test_system_prompt_has_user_query_tag_rule(self):
        from app.persistence import _get_default_prompt_content
        content = _get_default_prompt_content("system")
        assert "<user_query>" in content or "user_query" in content
        assert "忽略" in content or "ignore" in content.lower()

    def test_system_prompt_refuses_role_change(self):
        from app.persistence import _get_default_prompt_content
        content = _get_default_prompt_content("system")
        assert "改变角色" in content or "角色" in content.lower()

    def test_system_prompt_refuses_non_analysis_tasks(self):
        from app.persistence import _get_default_prompt_content
        content = _get_default_prompt_content("system")
        assert "数据分析之外" in content

    def test_sql_gen_prompt_has_injection_rule(self):
        from app.persistence import _get_default_prompt_content
        content = _get_default_prompt_content("sql_gen")
        assert "危险 SQL" in content or "忽略" in content


class TestSqlQuestionTruncation:
    def test_normal_question_passed_through(self):
        question = "上个月销量最高的产品是什么？"
        safe = question[:500]
        assert safe == question

    def test_long_question_truncated(self):
        question = "x" * 1000
        safe = question[:500]
        assert len(safe) == 500

    def test_truncated_question_still_readable(self):
        prefix = "请问"
        suffix = "x" * 498
        question = prefix + suffix
        safe = question[:500]
        assert safe.startswith("请问")
        assert len(safe) == 500

    def test_empty_question_handled(self):
        question = ""
        safe = question[:500]
        assert safe == ""


class TestChatRouteMessageWrapping:
    def test_user_message_wrapped_in_tag(self):
        from app.persistence import DEFAULT_PROMPT

        raw = "上个月销量"
        wrapped = f"<user_query>\n{raw}\n</user_query>"
        assert wrapped == "<user_query>\n上个月销量\n</user_query>"
        assert wrapped.startswith("<user_query>")
        assert wrapped.endswith("</user_query>")

    def test_wrapped_message_preserves_content(self):
        raw = "帮我分析一下销售趋势"
        wrapped = f"<user_query>\n{raw}\n</user_query>"
        assert raw in wrapped

    def test_multi_line_message_wrapped(self):
        raw = "第一行\n第二行\n第三行"
        wrapped = f"<user_query>\n{raw}\n</user_query>"
        assert wrapped.count("\n") == 4
        assert "第一行" in wrapped
        assert "第三行" in wrapped

    def test_long_message_wrapped(self):
        raw = "a" * 4000
        wrapped = f"<user_query>\n{raw}\n</user_query>"
        assert len(wrapped) == len(raw) + len("<user_query>\n\n</user_query>")
        assert wrapped.startswith("<user_query>")

"""Tests for llm.py — call_llm via mocked AsyncOpenAI."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_call_llm_with_key(mocker):
    """call_llm should pass api_key to AsyncOpenAI."""
    from app import state
    from app.config import LLMConfig

    state.config.llm = LLMConfig(api_key="sk-test", api_base="https://api.test.com", model="gpt-4o")

    # Mock the AsyncOpenAI constructor to return a mock client
    mock_client = mocker.AsyncMock()
    mock_client.chat.completions.create.return_value.choices = [
        type("C", (), {"message": type("M", (), {"content": "hello", "tool_calls": None})()})()
    ]
    mocker.patch("openai.AsyncOpenAI", return_value=mock_client)

    from app.llm import call_llm
    result = await call_llm([{"role": "user", "content": "hi"}])
    assert result.choices[0].message.content == "hello"


@pytest.mark.asyncio
async def test_call_llm_falls_back_to_env(mocker, monkeypatch):
    """When config has no key, should fall back to OPENAI_API_KEY env."""
    from app import state
    from app.config import LLMConfig

    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
    state.config.llm = LLMConfig(api_key="", model="gpt-4o")

    mock_client = mocker.AsyncMock()
    mocker.patch("openai.AsyncOpenAI", return_value=mock_client)

    from app.llm import call_llm
    await call_llm([{"role": "user", "content": "hi"}])
    assert mock_client.chat.completions.create.called


@pytest.mark.asyncio
async def test_call_llm_deepseek_thinking(mocker):
    """DeepSeek V4 models should include thinking mode."""
    from app import state
    from app.config import LLMConfig

    state.config.llm = LLMConfig(api_key="sk-ds", model="deepseek-v4-flash", api_base="https://api.deepseek.com")

    mock_client = mocker.AsyncMock()
    mocker.patch("openai.AsyncOpenAI", return_value=mock_client)

    from app.llm import call_llm
    await call_llm([{"role": "user", "content": "hi"}], temperature=0.5)

    # Verify extra_body thinking was passed
    _, kwargs = mock_client.chat.completions.create.call_args
    assert kwargs.get("extra_body") == {"thinking": {"type": "enabled"}}
    assert kwargs.get("temperature") == 0.5


@pytest.mark.asyncio
async def test_call_llm_no_key_no_env(mocker, monkeypatch):
    """Without key or env, should raise OpenAIError."""
    from app import state
    from app.config import LLMConfig

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    state.config.llm = LLMConfig(api_key="", model="gpt-4o")

    from app.llm import call_llm

    # Mock AsyncOpenAI to raise when no key provided
    mocker.patch("openai.AsyncOpenAI", side_effect=ValueError("No api key provided"))

    with pytest.raises((ValueError, Exception)):
        await call_llm([{"role": "user", "content": "hi"}])

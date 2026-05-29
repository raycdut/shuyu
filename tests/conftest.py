"""Shared fixtures for all backend tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def mock_llm_response():
    """Mock a successful LLM response with the given content."""
    class FakeChoice:
        class FakeMessage:
            def __init__(self, content):
                self.content = content
                self.tool_calls = None
        def __init__(self, content):
            self.message = self.FakeMessage(content)

    class FakeResponse:
        def __init__(self, content):
            self.choices = [FakeChoice(content)]

    return FakeResponse


@pytest.fixture
def mock_async_openai(mocker):
    """Mock AsyncOpenAI client."""
    mock_client = mocker.patch("openai.AsyncOpenAI", autospec=True)
    return mock_client

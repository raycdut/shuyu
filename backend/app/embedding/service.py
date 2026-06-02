"""Embedding service abstraction — supports pluggable providers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("shuyu.embedding")


class EmbeddingService(ABC):
    """Abstract embedding service."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...


class OpenAIEmbeddingService(EmbeddingService):
    """OpenAI text-embedding-* family via AsyncOpenAI client."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small", api_base: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self._client = None

    async def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            kwargs = {"api_key": self.api_key}
            if self.api_base:
                kwargs["base_url"] = self.api_base
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def embed(self, text: str) -> list[float]:
        client = await self._get_client()
        resp = await client.embeddings.create(model=self.model, input=text)
        return resp.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = await self._get_client()
        resp = await client.embeddings.create(model=self.model, input=texts)
        ordered = sorted(resp.data, key=lambda x: x.index)
        return [d.embedding for d in ordered]


class SiliconFlowEmbeddingService(EmbeddingService):
    """SiliconFlow API — China-friendly, supports BAAI/bge-m3 etc."""

    def __init__(self, api_key: str, model: str = "BAAI/bge-m3", api_base: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base or "https://api.siliconflow.cn/v1"

    async def _embed(self, input_data):
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key, base_url=self.api_base)
        return await client.embeddings.create(model=self.model, input=input_data)

    async def embed(self, text: str) -> list[float]:
        resp = await self._embed(text)
        return resp.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        resp = await self._embed(texts)
        ordered = sorted(resp.data, key=lambda x: x.index)
        return [d.embedding for d in ordered]


def create_embedding_service(provider: str, api_key: str, model: str, api_base: Optional[str] = None) -> EmbeddingService:
    """Factory: create embedding service by provider name."""
    if provider == "openai":
        return OpenAIEmbeddingService(api_key, model, api_base=api_base)
    elif provider == "siliconflow":
        return SiliconFlowEmbeddingService(api_key, model, api_base=api_base)
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")

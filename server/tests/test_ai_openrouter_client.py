from __future__ import annotations

import asyncio

import pytest

from ai.contracts import AIModelProfile, AIProviderConfig
from ai.openrouter_client import OpenRouterClient

pytestmark = pytest.mark.no_db


class FakeTransport:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[dict] = []

    async def __call__(self, *, method: str, url: str, headers: dict, json: dict, timeout: float) -> dict:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return self.payload


def test_openrouter_chat_completion_constructs_safe_request() -> None:
    async def run() -> None:
        transport = FakeTransport({"choices": [{"message": {"content": "Готово"}}]})
        client = OpenRouterClient(
            AIProviderConfig(
                provider_id="provider-1",
                code="openrouter-main",
                base_url="https://openrouter.ai/api/v1",
                api_key="sk-test-secret",
            ),
            transport=transport,
        )
        profile = AIModelProfile(
            profile_id="profile-1",
            provider_id="provider-1",
            task_type="answer",
            model_name="openai/gpt-4o-mini",
            timeout_ms=25_000,
            temperature=0.2,
        )

        result = await client.chat_completion(
            profile,
            messages=[{"role": "user", "content": "Как подключить VPN?"}],
            metadata={"ticket_id": "T-000001"},
        )

        assert result.output_text == "Готово"
        assert transport.calls == [
            {
                "method": "POST",
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "headers": {
                    "Authorization": "Bearer sk-test-secret",
                    "Content-Type": "application/json",
                },
                "json": {
                    "model": "openai/gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Как подключить VPN?"}],
                    "temperature": 0.2,
                    "metadata": {"ticket_id": "T-000001"},
                },
                "timeout": 25.0,
            }
        ]
        assert "sk-test-secret" not in repr(result)

    asyncio.run(run())


def test_openrouter_embedding_constructs_safe_request() -> None:
    async def run() -> None:
        transport = FakeTransport({"data": [{"embedding": [0.1, 0.2, 0.3]}]})
        client = OpenRouterClient(
            AIProviderConfig(
                provider_id="provider-1",
                code="openrouter-main",
                base_url="https://openrouter.ai/api/v1/",
                api_key="sk-test-secret",
            ),
            transport=transport,
        )
        profile = AIModelProfile(
            profile_id="profile-embed",
            provider_id="provider-1",
            task_type="embedding",
            model_name="openai/text-embedding-3-small",
            timeout_ms=10_000,
        )

        result = await client.generate_embedding(profile, input_text="VPN не подключается")

        assert result.embedding == [0.1, 0.2, 0.3]
        assert transport.calls[0]["url"] == "https://openrouter.ai/api/v1/embeddings"
        assert transport.calls[0]["json"] == {
            "model": "openai/text-embedding-3-small",
            "input": "VPN не подключается",
        }

    asyncio.run(run())


def test_openrouter_rerank_constructs_safe_request() -> None:
    async def run() -> None:
        transport = FakeTransport({"results": [{"index": 1, "relevance_score": 0.91}]})
        client = OpenRouterClient(
            AIProviderConfig(
                provider_id="provider-1",
                code="openrouter-main",
                base_url="https://openrouter.ai/api/v1",
                api_key="sk-test-secret",
            ),
            transport=transport,
        )
        profile = AIModelProfile(
            profile_id="profile-rerank",
            provider_id="provider-1",
            task_type="rerank",
            model_name="cohere/rerank-v3.5",
            timeout_ms=12_000,
        )

        result = await client.rerank(profile, query="vpn", documents=["one", "two"])

        assert result.results == [{"index": 1, "relevance_score": 0.91}]
        assert transport.calls[0]["url"] == "https://openrouter.ai/api/v1/rerank"
        assert transport.calls[0]["json"] == {
            "model": "cohere/rerank-v3.5",
            "query": "vpn",
            "documents": ["one", "two"],
        }

    asyncio.run(run())

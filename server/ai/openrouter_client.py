from __future__ import annotations

from typing import Any, Awaitable, Callable

from ai.contracts import AIEmbeddingResult, AIModelProfile, AIProviderConfig, AIRerankResult, AITextResult

Transport = Callable[..., Awaitable[dict[str, Any]]]


class OpenRouterClient:
    def __init__(self, provider: AIProviderConfig, *, transport: Transport):
        self.provider = provider
        self.transport = transport

    def _url(self, path: str) -> str:
        return f"{self.provider.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.provider.api_key:
            headers["Authorization"] = f"Bearer {self.provider.api_key}"
        return headers

    @staticmethod
    def _timeout_seconds(profile: AIModelProfile) -> float:
        return max(1, int(profile.timeout_ms or 30_000)) / 1000.0

    async def chat_completion(
        self,
        profile: AIModelProfile,
        *,
        messages: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> AITextResult:
        payload: dict[str, Any] = {
            "model": profile.model_name,
            "messages": messages,
        }
        if profile.temperature is not None:
            payload["temperature"] = profile.temperature
        if profile.top_p is not None:
            payload["top_p"] = profile.top_p
        if metadata:
            payload["metadata"] = metadata
        raw = await self.transport(
            method="POST",
            url=self._url("chat/completions"),
            headers=self._headers(),
            json=payload,
            timeout=self._timeout_seconds(profile),
        )
        choices = raw.get("choices") if isinstance(raw, dict) else None
        content = ""
        if choices and isinstance(choices, list):
            first = choices[0] if choices else {}
            message = first.get("message") if isinstance(first, dict) else {}
            content = str((message or {}).get("content") or "")
        return AITextResult(output_text=content, raw=raw)

    async def generate_embedding(self, profile: AIModelProfile, *, input_text: str) -> AIEmbeddingResult:
        raw = await self.transport(
            method="POST",
            url=self._url("embeddings"),
            headers=self._headers(),
            json={"model": profile.model_name, "input": input_text},
            timeout=self._timeout_seconds(profile),
        )
        data = raw.get("data") if isinstance(raw, dict) else None
        first = data[0] if isinstance(data, list) and data else {}
        embedding = first.get("embedding") if isinstance(first, dict) else []
        return AIEmbeddingResult(embedding=list(embedding or []), raw=raw)

    async def rerank(self, profile: AIModelProfile, *, query: str, documents: list[str]) -> AIRerankResult:
        raw = await self.transport(
            method="POST",
            url=self._url("rerank"),
            headers=self._headers(),
            json={"model": profile.model_name, "query": query, "documents": documents},
            timeout=self._timeout_seconds(profile),
        )
        results = raw.get("results") if isinstance(raw, dict) else []
        return AIRerankResult(results=list(results or []), raw=raw)

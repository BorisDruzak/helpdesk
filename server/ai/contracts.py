from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AIProviderConfig:
    provider_id: str
    code: str
    base_url: str
    api_key: str | None = None

    def __repr__(self) -> str:
        return f"AIProviderConfig(provider_id={self.provider_id!r}, code={self.code!r}, base_url={self.base_url!r})"


@dataclass(frozen=True)
class AIModelProfile:
    profile_id: str
    provider_id: str
    task_type: str
    model_name: str
    timeout_ms: int = 30_000
    temperature: float | None = None
    top_p: float | None = None


@dataclass(frozen=True)
class AITextResult:
    output_text: str
    raw: dict[str, Any]

    def __repr__(self) -> str:
        return f"AITextResult(output_text={self.output_text!r})"


@dataclass(frozen=True)
class AIEmbeddingResult:
    embedding: list[float]
    raw: dict[str, Any]

    def __repr__(self) -> str:
        return f"AIEmbeddingResult(dimensions={len(self.embedding)})"


@dataclass(frozen=True)
class AIRerankResult:
    results: list[dict[str, Any]]
    raw: dict[str, Any]

    def __repr__(self) -> str:
        return f"AIRerankResult(results={len(self.results)})"

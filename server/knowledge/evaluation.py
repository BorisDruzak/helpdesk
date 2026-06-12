from __future__ import annotations

from typing import Any


class KnowledgeEvalRecorder:
    """Small test/eval helper for repeatable Knowledge search and RAG safety metrics."""

    def __init__(self) -> None:
        self.search_cases = 0
        self.search_hits = 0
        self.no_answer_cases = 0
        self.no_answer_hits = 0
        self.citation_cases = 0
        self.allowed_citations = 0
        self.total_citations = 0
        self.acl_leakage_count = 0
        self.fallback_count = 0
        self.provider_failure_count = 0
        self.case_results: list[dict[str, Any]] = []

    def record_search_case(self, name: str, *, expected_slugs: set[str], results: list[dict[str, Any]], top_k: int = 5) -> None:
        returned = {str(item.get("slug") or item.get("item", {}).get("slug") or "") for item in results[:top_k]}
        hit = bool(expected_slugs & returned)
        self.search_cases += 1
        self.search_hits += int(hit)
        self.case_results.append({"name": name, "kind": "search", "hit": hit, "expected_slugs": sorted(expected_slugs), "returned_slugs": sorted(returned)})

    def record_acl_case(self, name: str, *, forbidden_visibilities: set[str], results: list[dict[str, Any]]) -> None:
        leaks = []
        for result in results:
            visibility = str(result.get("visibility") or result.get("item", {}).get("visibility") or "")
            if visibility in forbidden_visibilities:
                leaks.append({"slug": result.get("slug") or result.get("item", {}).get("slug"), "visibility": visibility})
        self.acl_leakage_count += len(leaks)
        self.case_results.append({"name": name, "kind": "acl", "leak_count": len(leaks), "leaks": leaks})

    def record_no_answer_case(self, name: str, result: dict[str, Any]) -> None:
        status = str(result.get("answer_status") or "")
        hit = status == "not_enough_evidence"
        self.no_answer_cases += 1
        self.no_answer_hits += int(hit)
        self._record_fallback_status(status)
        self.case_results.append({"name": name, "kind": "no_answer", "hit": hit, "answer_status": status})

    def record_citation_case(self, name: str, *, allowed_item_ids: set[str], citations: list[dict[str, Any]]) -> None:
        self.citation_cases += 1
        allowed = 0
        for citation in citations:
            if str(citation.get("item_id") or "") in allowed_item_ids:
                allowed += 1
        self.allowed_citations += allowed
        self.total_citations += len(citations)
        self.case_results.append({"name": name, "kind": "citations", "allowed": allowed, "total": len(citations)})

    def report(self, *, latency_ms: int | float = 0) -> dict[str, Any]:
        citation_precision = 1.0 if self.total_citations == 0 else self.allowed_citations / self.total_citations
        return {
            "metrics": {
                "top_k_recall": 0.0 if self.search_cases == 0 else self.search_hits / self.search_cases,
                "citation_precision": citation_precision,
                "no_answer_correctness": 0.0 if self.no_answer_cases == 0 else self.no_answer_hits / self.no_answer_cases,
                "acl_leakage_count": self.acl_leakage_count,
                "fallback_count": self.fallback_count,
                "latency_ms": latency_ms,
                "provider_failure_count": self.provider_failure_count,
            },
            "cases": list(self.case_results),
        }

    def _record_fallback_status(self, status: str) -> None:
        if status and status != "answered":
            self.fallback_count += 1
        if status == "provider_unavailable":
            self.provider_failure_count += 1

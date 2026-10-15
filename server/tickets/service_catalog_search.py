"""Bounded deterministic search of the requester-safe, published catalog only.

This module intentionally has no repository access: authorization and immutable
entrance projection are owned by ServiceCatalogRuntimeResolver, before ranking.
"""
from __future__ import annotations

import re
from typing import Any

_NEGATIONS = {"не", "нет", "без"}
_STOP_WORDS = {"в", "во", "с", "со", "на", "по", "к", "и", "для", "из", "у"}
_ENDINGS = re.compile(r"(иями|ями|ами|ого|ему|ому|ыми|ими|ать|ять|ить|ает|яют|ают|ете|ется|ются|ая|яя|ое|ее|ой|ий|ый|ом|ем|ым|им|ую|юю|ах|ях|ам|ям|ов|ев|ей|а|я|е|о|у|ы|и|ь)$")
_LAYOUT = str.maketrans("qwertyuiop[]asdfghjkl;'zxcvbnm,.", "йцукенгшщзхъфывапролджэячсмитьбю")
_REASONS = ("Точное название", "Совпала ключевая фраза", "Совпало дополнительное поисковое выражение",
            "Совпали слова запроса", "Совпала часть слова", "Возможно, в запросе опечатка")


def _normalize(value: Any) -> str:
    return " ".join(re.findall(r"[\w]+", str(value or "").casefold().replace("ё", "е"), re.UNICODE))


def _tokens(value: str) -> list[str]:
    return [token for token in value.split() if token not in _STOP_WORDS]


def _stem(word: str) -> str:
    stem = _ENDINGS.sub("", word)
    return stem if len(stem) >= 4 else word


def _one_edit(left: str, right: str) -> bool:
    """At most one substitution, insertion, deletion or adjacent transposition."""
    if min(len(left), len(right)) < 4 or abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        differences = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
        return len(differences) <= 1 or (len(differences) == 2 and differences[1] == differences[0] + 1
            and left[differences[0]] == right[differences[1]] and left[differences[1]] == right[differences[0]])
    short, long = sorted((left, right), key=len)
    mismatch = next((i for i, (a, b) in enumerate(zip(short, long)) if a != b), len(short))
    return short[mismatch:] == long[mismatch + 1:]


def _word_match(query: str, word: str) -> int | None:
    if query == word or (_stem(query) == _stem(word) and len(_stem(query)) >= 4):
        return 3
    # Negations and short function words must never be manufactured by fuzziness.
    if query in _NEGATIONS or word in _NEGATIONS:
        return None
    if len(query) >= 3 and word.startswith(query):
        return 4
    if len(query) <= 64 and len(word) <= 64 and _one_edit(query, word):
        return 5
    return None


def _field_rank(query: str, field: str, kind: str) -> int | None:
    words, requested = _tokens(field), _tokens(query)
    if not words or not requested or set(words) & _NEGATIONS != set(requested) & _NEGATIONS:
        return None
    if query == field:
        return 0 if kind == "title" else 2 if kind == "synonym" else 1
    if f" {query} " in f" {field} ":
        return 2 if kind == "synonym" else 1
    matches = [min((rank for word in words if (rank := _word_match(token, word)) is not None), default=99)
               for token in requested]
    return max(matches) if max(matches) < 99 else None


def _documents(catalog: dict[str, Any]):
    for service in catalog.get("services", []):
        for offering in service.get("offerings", []):
            # Entries have already passed scenario/category/entrance ACL checks.
            entries = offering.get("catalog_items", [])
            if not entries:
                entries = [{"title": offering.get("title"), "description": offering.get("description"),
                            "help_mode": "guided" if offering.get("guided_scenario_enabled") else "request"}]
            for entry in entries:
                yield service, offering, entry


def search_public_catalog(catalog: dict[str, Any], query: str, *, limit: int = 20) -> dict[str, Any]:
    """Never use this function with unfiltered admin/draft records."""
    normalized = _normalize(query)
    result = {"query": str(query)[:200], "corrected_query": None, "results": [], "suggestions": []}
    if not normalized or len(query) > 200 or len(_tokens(normalized)) > 20:
        return result
    variants = [(normalized, False)]
    corrected = _normalize(str(query).casefold().translate(_LAYOUT))
    if re.search(r"[a-z]", normalized) and corrected != normalized:
        variants.append((corrected, True))
    ranked = []
    for service, offering, entry in _documents(catalog):
        fields = [("title", _normalize(entry.get("title"))), ("description", _normalize(entry.get("description")))]
        fields.extend(("synonym", _normalize(synonym)) for synonym in entry.get("synonyms", []))
        matches = [(rank, corrected_layout) for value, corrected_layout in variants for kind, field in fields
                   if (rank := _field_rank(value, field, kind)) is not None]
        if not matches:
            continue
        rank, layout = min(matches, key=lambda match: (match[0] + (6 if match[1] else 0), match[1]))
        row = {"title": entry.get("title") or offering.get("title"),
               "description": entry.get("description") or "", "category": entry.get("category_title") or service.get("title"),
               "service_code": service.get("service_code"), "offering_full_code": offering.get("full_code"),
               "entry_point_key": entry.get("entry_point_key"), "help_mode": entry.get("help_mode") or "guided",
               "match_reason": "Исправлена раскладка клавиатуры" if layout else _REASONS[rank]}
        ranked.append((rank + (6 if layout else 0), _normalize(row["title"]), str(row["offering_full_code"]),
                       str(row["entry_point_key"] or ""), row, layout))
    ranked.sort(key=lambda item: item[:4])
    selected = ranked[:max(1, min(limit, 50))]
    result["results"] = [item[4] for item in selected]
    if selected and selected[0][5]:
        result["corrected_query"] = corrected
    if selected and selected[0][0] >= 4:
        result["suggestions"] = list(dict.fromkeys(item[4]["title"] for item in selected))[:3]
    return result

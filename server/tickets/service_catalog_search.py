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
            "Совпали слова запроса", "Совпала часть слова", "Возможно, в запросе опечатка",
            "Подходит по описанию неисправности", "Услуга подходит — выберите проблему")
# Explicit negative/abnormal phrases only: never discard negation from arbitrary text.
_CANNOT = r"не (?:могу|можем|может|удается|получается) "
_SYMPTOMS = {key: re.compile(r"\b(?:" + pattern + r")\b") for key, pattern in {
    "failure": r"не ?работа(?:ет|ют|л|ла|ло|ли)|не функционирует|перестал(?:а|о|и)? работать|сломал(?:ся|ась|ось|ись)",
    "startup": r"не ?(?:включа|запуска|загружа)(?:ется|ются)|не стартует|" + _CANNOT + r"(?:включить|запустить|загрузить)",
    "opening": r"не ?открыва(?:ется|ются|ет|ют)|" + _CANNOT + r"открыть",
    "login": _CANNOT + r"(?:войти|авторизоваться)|не (?:входит|пускает)|ошибка входа|нет доступа|доступ запрещен|учетная запись заблокирована",
    "printing": r"не печата(?:ет|ют|ется|ются)|" + _CANNOT + r"(?:распечатать|напечатать)|ошибка печати|не идет печать",
    "signing": r"не подписыва(?:ет|ют|ется|ются)|" + _CANNOT + r"подписать|ошибка (?:электронной )?подписи",
    "connection": r"не подключа(?:ется|ются)|" + _CANNOT + r"подключиться|нет (?:интернета|сети|подключения)|пропал интернет",
    "slow": r"тормоз(?:ит|ят)|завис(?:ает|ают|ло|ла|ли)|работает медленно|медленно работает",
    "error": r"ошибка|сбой|поломка|неисправность|недоступен|недоступна|недоступно|недоступны",
}.items()}
_OTHER_FAILURE = re.compile(r"\b(?:не (?:отправля|приход|сохраня|сканиру|синхронизиру|определя|вид)(?:\w*)|отключен|прерывается)\b")
_CONVERSATION_WORDS = {"меня", "нас", "мне", "нам", "мой", "моя", "мое", "мои", "пожалуйста", "помогите", "почему", "сейчас", "совсем", "все"}


def _symptom_spans(value: str) -> list[tuple[int, int, str]]:
    # A specific phrase such as "ошибка входа" wins over its generic "ошибка".
    matches = sorted(((m.start(), m.end(), intent) for intent, pattern in _SYMPTOMS.items()
                      for m in pattern.finditer(value)), key=lambda item: (item[0] - item[1], item[0], item[2]))
    selected: list[tuple[int, int, str]] = []
    for start, end, intent in matches:
        if not any(start < right and end > left for left, right, _ in selected):
            selected.append((start, end, intent))
    return selected


def _symptom_query(query: str) -> tuple[set[str], list[str]]:
    """Recognize bounded phrases and retain every meaningful device/system word."""
    spans = _symptom_spans(query)
    intents = {intent for _, _, intent in spans}
    covered = {i for start, end, _ in spans for i in range(start, end)}
    remainder = "".join(" " if i in covered else char for i, char in enumerate(query))
    # "Нет интернета" is specifically about internet, not every connection.
    retained = [word for start, end, intent in spans if intent == "connection"
                for word in re.findall(r"\b(?:интернет|интернета|сети)\b", query[start:end])]
    return intents, [word for word in [*_tokens(remainder), *retained] if word not in _CONVERSATION_WORDS]


def _context_rank(requested: list[str], fields: list[str]) -> int | None:
    words = [word for field in fields for word in _tokens(field)]
    matches = [min((rank for word in words if (rank := _word_match(token, word)) is not None), default=99)
               for token in requested]
    return max(matches, default=3) if max(matches, default=3) < 99 else None


def _symptom_rank(intents: set[str], anchors: list[str], fields: list[str], offering_title: str,
                  *, service_row: bool) -> int | None:
    if not intents or set(anchors) & _NEGATIONS:
        return None
    if _context_rank(anchors, [offering_title, *fields]) is None:
        return None
    target = {intent for field in fields for _, _, intent in _symptom_spans(field)}
    related = bool(intents & target) or ("failure" in intents and (target or any(_OTHER_FAILURE.search(field) for field in fields)))
    if related and (not service_row or not anchors):
        return 6
    # The named service can still help when it has no matching published entrance.
    if anchors and service_row and _context_rank(anchors, [offering_title]) is not None:
        return 7
    return None


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
            if entries:
                yield service, offering, {"title": offering.get("title"), "description": offering.get("description"),
                    "help_mode": "guided" if offering.get("guided_scenario_enabled") else "request", "result_kind": "service"}
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
    semantic = [(value, layout, *_symptom_query(value)) for value, layout in variants]
    ranked = []
    for service, offering, entry in _documents(catalog):
        fields = [("title", _normalize(entry.get("title"))), ("description", _normalize(entry.get("description")))]
        if entry.get("result_kind") == "service":
            fields.append(("category", _normalize(service.get("title"))))
        fields.extend(("synonym", _normalize(synonym)) for synonym in entry.get("synonyms", []))
        matches = [(rank, corrected_layout) for value, corrected_layout in variants for kind, field in fields
                   if (rank := _field_rank(value, field, kind)) is not None]
        symptom_matches = [(rank, layout) for _, layout, intents, anchors in semantic
                           if (rank := _symptom_rank(intents, anchors, [field for _, field in fields], _normalize(offering.get("title")),
                                                    service_row=entry.get("result_kind") == "service")) is not None]
        # Unrelated fragments such as "начала работы ... пароли не указывайте"
        # are not a failure phrase, even if the older lexical matcher accepts them.
        if (any(intents and not anchors for _, _, intents, anchors in semantic) and not symptom_matches
                and not any(rank <= 2 for rank, _ in matches)):
            continue
        matches.extend(symptom_matches)
        if not matches:
            continue
        rank, layout = min(matches, key=lambda match: (match[0] + (6 if match[1] else 0), match[1]))
        row = {"title": entry.get("title") or offering.get("title"),
               "description": entry.get("description") or "", "category": entry.get("category_title") or service.get("title"),
               "service_code": service.get("service_code"), "offering_full_code": offering.get("full_code"),
               "offering_title": offering.get("title") or "",
               "entry_point_key": entry.get("entry_point_key"), "help_mode": entry.get("help_mode") or "guided",
               "result_kind": entry.get("result_kind") or "problem",
               "match_reason": "Исправлена раскладка клавиатуры" if layout else _REASONS[rank]}
        ranked.append((rank + (6 if layout else 0), _normalize(row["title"]), str(row["offering_full_code"]),
                       str(row["entry_point_key"] or ""), row, layout))
    ranked.sort(key=lambda item: item[:4])
    if any(intents and not anchors for _, _, intents, anchors in semantic):
        # First show one useful entrance per service; only then repeat a service.
        occurrences: dict[str, int] = {}
        diversified = []
        for item in ranked:
            code = item[2]
            occurrence = occurrences.get(code, 0)
            occurrences[code] = occurrence + 1
            diversified.append((occurrence, item))
        ranked = [item for _, item in sorted(diversified, key=lambda pair: (pair[0], pair[1][:4]))]
    selected = ranked[:max(1, min(limit, 50))]
    result["results"] = [item[4] for item in selected]
    if selected and selected[0][5]:
        result["corrected_query"] = corrected
    if selected and selected[0][0] >= 4:
        result["suggestions"] = list(dict.fromkeys(item[4]["title"] for item in selected))[:3]
    return result

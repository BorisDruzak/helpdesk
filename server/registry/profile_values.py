"""Strict profile writes; legacy reads never coerce or rewrite stored values."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from urllib.parse import urlsplit


CONTACT_OPTIONS = [
    {"value": "phone", "label": "Телефон"},
    {"value": "chat", "label": "Чат в обращении"},
    {"value": "email", "label": "Электронная почта"},
]


def safe_pattern(pattern: str) -> re.Pattern:
    """Full-match, no groups/alternation/backrefs; at most one variable repeat.

    Input and pattern lengths are bounded. This deliberately small grammar avoids
    exponential and polynomial backtracking without another regex dependency.
    """
    if not isinstance(pattern, str) or len(pattern) > 200:
        raise ValueError("Шаблон должен содержать не более 200 символов.")
    body = pattern.removeprefix("^").removesuffix("$")
    token = re.compile(r"(?:\[(?:\\[dDsSwW\\\]\-]|[^\[\]\\])+\]|\\[dDsSwW.\-+*?{}\[\]\\]|[^\[\]\\()|^$.*+?{}])(?:[+*?]|\{\d{1,4}(?:,\d{1,4})?\})?")
    cursor = 0
    variable_repeats = 0
    while cursor < len(body):
        match = token.match(body, cursor)
        if match is None:
            raise ValueError("Шаблон: допустимы символы, классы и одно повторение; группы и альтернативы не поддерживаются.")
        part = match.group()
        quantifier = re.search(r"(?<!\\)([+*?]|\{(\d+)(?:,(\d+))?\})$", part)
        if quantifier:
            low, high = quantifier.group(2), quantifier.group(3)
            if low and (int(low) > 1000 or high and (int(high) > 1000 or int(high) < int(low))):
                raise ValueError("Число повторений в шаблоне должно быть от 0 до 1000.")
            variable_repeats += int(not low or high is not None and high != low)
        cursor = match.end()
    if not body or variable_repeats > 1:
        raise ValueError("Допустимо не более одного переменного повторения в шаблоне.")
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise ValueError("Некорректный шаблон проверки.") from exc


def clean_profile_value(field: dict[str, Any], value: Any) -> Any:
    if value is None or value == "":
        return None
    kind = field.get("type")
    if kind == "checkbox":
        if type(value) is not bool:
            raise ValueError("Укажите явное логическое значение.")
        return value
    if kind == "number":
        if type(value) not in {str, int, float} or isinstance(value, str) and not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value.strip()):
            raise ValueError("Укажите число.")
        if len(str(value)) > 100:
            raise ValueError("Число слишком велико.")
        try:
            number = Decimal(str(value).strip())
            if not number.is_finite() or abs(number) > Decimal(2**53 - 1):
                raise ValueError("Укажите конечное число в допустимом диапазоне.")
            return int(number) if number == number.to_integral_value() else float(number)
        except (InvalidOperation, OverflowError) as exc:
            raise ValueError("Укажите число.") from exc
    if not isinstance(value, str):
        raise ValueError("Укажите строковое значение.")
    text = value.strip()
    if not text:
        return None
    validation = field.get("validation") or {}
    maximum = validation.get("max_length", 1000 if kind == "textarea" else 500)
    if len(value) > maximum:
        raise ValueError(f"Не более {maximum} символов.")
    if len(text) < validation.get("min_length", 0):
        raise ValueError(f"Не менее {validation['min_length']} символов.")
    if any(ord(ch) < 32 and not (kind == "textarea" and ch in "\r\n\t") for ch in text):
        raise ValueError("Недопустимые управляющие символы.")
    if kind == "select":
        allowed = [item.get("value") if isinstance(item, dict) else item for item in field.get("options") or []]
        if text not in allowed:
            raise ValueError("Выберите действующий вариант списка.")
    elif kind == "phone":
        if not re.fullmatch(r"[\d\s+().,#*\-xXextдоб]+", text) or not any(ch.isdecimal() for ch in text):
            raise ValueError("Укажите телефон или внутренний номер.")
    elif kind == "email":
        if not re.fullmatch(r"[^\s@<>]+@[^\s@<>.]+(?:\.[^\s@<>.]+)+", text):
            raise ValueError("Укажите корректный адрес электронной почты.")
    elif kind == "url":
        try:
            parts = urlsplit(text)
            valid = (parts.scheme in {"http", "https"} and parts.hostname
                     and not parts.username and not parts.password and parts.port != 0
                     and not re.search(r"[\s\\]", text))
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Укажите HTTP(S) ссылку без учетных данных.")
    elif kind == "date":
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                raise ValueError
            date.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("Укажите действительную дату в формате ГГГГ-ММ-ДД.") from exc
    pattern = validation.get("pattern")
    if pattern and not safe_pattern(pattern).fullmatch(text):
        raise ValueError("Значение не соответствует шаблону поля.")
    return text

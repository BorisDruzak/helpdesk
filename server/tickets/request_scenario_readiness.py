"""Bounded exhaustive finite facts using the canonical scenario evaluator.

Readiness fails closed when process inputs have an unbounded domain. Ordinary
description fields use one validated representative; they cannot affect policy.
"""
from itertools import product, combinations, permutations
from math import perm, nextafter

from tickets.request_scenario_conditions import leaves, finite_number
from tickets.request_scenario_runtime import ScenarioRuntime, ScenarioInputError
from tickets.request_scenario_validation import DIAGNOSTIC_FAILURE_STATUSES
from web_api.dto.request_scenario import ScenarioAnswerRequest


class ReadinessCoverageError(ValueError):
    pass


_OMITTED = object()


def _representative(field):
    if field.type == "number":
        lower = field.validation.min_value
        upper = field.validation.max_value
        return max(lower if lower is not None else -9007199254740991, min(1, upper if upper is not None else 9007199254740991))
    defaults = {"multi_select": [field.options[0].value] if field.options else [], "email": "test@example.invalid",
                "phone": "+70000000000", "url": "https://example.invalid", "date": "2026-01-01", "datetime": "2026-01-01T12:00:00"}
    value = defaults.get(field.type, "Проверка сценария")
    if field.type in {"text", "textarea"}:
        length = max(field.validation.min_length or 1, min(len(value), field.validation.max_length or 10000))
        value = (value * (length // len(value) + 1))[:length]
    return value


def _condition_domain(field, conditions):
    """Truth-equivalent representatives for graph-only scalar comparisons.

    This partition proves graph conditions, never arbitrary policy behavior.
    Numeric cuts include boundaries and each representable open interval;
    string predicates are equality/membership/exists, so one other nonempty
    string covers the complement of their finite literals.
    """
    literals = [value for condition in conditions for value in (condition.value if condition.op == "in" else [getattr(condition, "value", None)])]
    if field.type == "number":
        lower = max(-9007199254740991, field.validation.min_value if field.validation.min_value is not None else -9007199254740991)
        upper = min(9007199254740991, field.validation.max_value if field.validation.max_value is not None else 9007199254740991)
        if lower > upper:
            return []
        cuts = sorted({lower, upper, *[value for value in literals if finite_number(value) and lower <= value <= upper]})
        values = list(cuts)
        for left, right in zip(cuts, cuts[1:]):
            middle = left + (right - left) / 2
            if not left < middle < right:
                middle = nextafter(left, right)
            if left < middle < right:
                values.append(middle)
        return values
    if field.type in {"text", "textarea"}:
        values = [value for value in literals if isinstance(value, str)]
        length = max(1, field.validation.min_length or 1)
        # More distinct candidates than literals ensures a non-literal value.
        other = next(chr(0x4E00 + index) * length for index in range(len(values) + 1) if chr(0x4E00 + index) * length not in values)
        return [*dict.fromkeys(values), other]
    raise ReadinessCoverageError(f"Поле «{field.label}»: для проверки условий нужен доказуемый набор вариантов.")


def submission_variants(definition, *, limit=512, process_fields=()):
    diagnostics = [block.id for block in definition.blocks if block.kind == "diagnostic"]
    if not diagnostics:
        return _submission_variants(definition, limit=limit, process_fields=process_fields)
    if len(DIAGNOSTIC_FAILURE_STATUSES) ** len(diagnostics) > limit:
        raise ReadinessCoverageError("Слишком много сочетаний диагностических исходов. Разделите сценарий для полной проверки.")
    terminals = []
    for values in product(DIAGNOSTIC_FAILURE_STATUSES, repeat=len(diagnostics)):
        states = _submission_variants(definition, limit=limit, process_fields=process_fields, diagnostic_outcomes=dict(zip(diagnostics, values)))
        for state in states:
            if state not in terminals:
                terminals.append(state)
            if len(terminals) > limit:
                raise ReadinessCoverageError("Слишком много сочетаний ответов и диагностических исходов. Разделите сценарий для полной проверки.")
    return terminals


def _submission_variants(definition, *, limit, process_fields, diagnostic_outcomes=None):
    runtime = ScenarioRuntime(definition, diagnostic_outcomes=diagnostic_outcomes)
    referenced = {}
    for block in definition.blocks:
        conditions = [edge.when for edge in block.transitions]
        for field in getattr(block, "fields", ()):
            conditions.extend([field.visible_when, field.required_when])
        for condition in conditions:
            for leaf in leaves(condition):
                if leaf.source == "answer":
                    referenced.setdefault(leaf.field, []).append(leaf)
    domains = {}
    for block in definition.blocks:
        for field in getattr(block, "fields", ()):
            policy_input = field.key in process_fields or any(role in {"priority_impact", "priority_urgency", "priority_importance", "routing_field", "approval_subject"} for role in field.process_mapping.roles)
            significant = field.key in referenced or policy_input
            if field.type in {"select", "radio"}:
                values = [option.value for option in field.options]
            elif field.type == "checkbox":
                values = [False, True]
            elif field.type == "multi_select" and significant:
                size_count = len(field.options)
                count = sum(perm(size_count, size) for size in range(size_count + 1)) if policy_input else 2 ** size_count
                if count > limit:
                    raise ReadinessCoverageError("Слишком много сочетаний множественного выбора. Разделите варианты.")
                choices = [option.value for option in field.options]
                enumerate_choices = permutations if policy_input else combinations
                values = [list(subset) for size in range(len(choices) + 1) for subset in enumerate_choices(choices, size)]
            elif field.key in referenced and not policy_input:
                values = _condition_domain(field, referenced[field.key])
            elif significant:
                raise ReadinessCoverageError(f"Поле «{field.label}»: для проверки всех исходов обработки нужен конечный набор вариантов.")
            else:
                values = [_representative(field)]
            if not significant:
                values = values[:1]
            if significant and (field.allow_unknown or not field.required):
                values = [*values, None]
            if significant and not field.required:
                values = [*values, _OMITTED]
            domains[field.key] = values
    pending, terminals, traversed = [runtime.initial_state()], [], 0
    while pending:
        state = pending.pop()
        traversed += 1
        if traversed > limit * max(1, len(definition.blocks)) or len(pending) + len(terminals) > limit:
            raise ReadinessCoverageError("Слишком много сочетаний ответов. Разделите сценарий для полной проверки.")
        block = runtime.blocks[state.current_block_id]
        if block.kind in {"finish", "submit_ticket"}:
            terminals.append(state)
            continue
        variants = [({}, None)]
        if block.kind == "form_page":
            fields = block.fields
            count = 1
            for field in fields:
                count *= len(domains[field.key])
                if count > limit:
                    raise ReadinessCoverageError("Слишком много сочетаний на странице. Разделите вопросы.")
            variants = [({field.key: value for field, value in zip(fields, values) if value is not _OMITTED}, None) for values in product(*(domains[field.key] for field in fields))]
        elif block.kind == "resolution_check":
            variants = [({}, value) for value in ("yes", "no", "unknown")]
        elif block.kind == "instruction":
            variants = [({}, "acknowledged")] if block.acknowledgment_required else [({}, None), ({}, "acknowledged")]
            if runtime.can_request_ticket(state):
                variants.append(({}, "request_ticket"))
        advanced = []
        for answers, result in variants:
            try:
                next_state = runtime.advance(state, ScenarioAnswerRequest(expected_block_id=block.id, revision=state.revision, answers=answers, current_result=result))
            except ScenarioInputError:
                continue  # Invalid/hidden/required combinations are not executable paths.
            if next_state not in advanced:
                advanced.append(next_state)
        if not advanced:
            raise ReadinessCoverageError(f"Шаг «{block.title}»: нет проверяемого допустимого ответа.")
        pending.extend(advanced)
    return terminals

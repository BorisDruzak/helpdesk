"""Bounded exhaustive finite facts using the canonical scenario evaluator.

Readiness fails closed when process inputs have an unbounded domain. Ordinary
description fields use one validated representative; they cannot affect policy.
"""
from itertools import product

from tickets.request_scenario_conditions import leaves
from tickets.request_scenario_runtime import ScenarioRuntime, ScenarioInputError
from web_api.dto.request_scenario import ScenarioAnswerRequest


class ReadinessCoverageError(ValueError):
    pass


def submission_variants(definition, *, limit=512, process_fields=()):
    runtime = ScenarioRuntime(definition)
    referenced = set()
    for block in definition.blocks:
        conditions = [edge.when for edge in block.transitions]
        for field in getattr(block, "fields", ()):
            conditions.extend([field.visible_when, field.required_when])
        referenced.update(leaf.field for condition in conditions for leaf in leaves(condition) if leaf.source == "answer")
    domains = {}
    for block in definition.blocks:
        for field in getattr(block, "fields", ()):
            significant = field.key in referenced or field.key in process_fields or any(role in {"priority_impact", "priority_urgency", "priority_importance", "routing_field", "approval_subject"} for role in field.process_mapping.roles)
            if field.type in {"select", "radio"}:
                values = [option.value for option in field.options]
            elif field.type == "checkbox":
                values = [False, True]
            elif significant:
                raise ReadinessCoverageError(f"Поле «{field.label}»: для проверки всех исходов обработки нужен конечный набор вариантов.")
            else:
                defaults = {"number": 1, "multi_select": [field.options[0].value] if field.options else [], "email": "test@example.invalid",
                            "phone": "+70000000000", "date": "2026-01-01", "datetime": "2026-01-01T12:00:00"}
                values = [defaults.get(field.type, "Проверка сценария")]
            if not significant:
                values = values[:1]
            if significant and (field.allow_unknown or not field.required):
                values = [*values, None]
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
            variants = [(dict(zip([f.key for f in fields], values)), None) for values in product(*(domains[f.key] for f in fields))]
        elif block.kind == "resolution_check":
            variants = [({}, value) for value in ("yes", "no", "unknown")]
        elif block.kind == "instruction":
            variants = [({}, "acknowledged")] if block.acknowledgment_required else [({}, None), ({}, "acknowledged")]
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

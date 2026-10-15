"""Translate a validated, pinned session into trusted canonical create inputs."""
from copy import deepcopy

from tickets.request_scenario_runtime import ScenarioInputError, ScenarioRuntime
from tickets.request_scenario_session import project_step


def derive_scenario_form(definition, state):
    """Project only the current retained route into canonical FormSchema fields."""
    from tickets.request_scenario_conditions import evaluate_condition
    blocks = {block.id: block for block in definition.blocks}
    fields = []
    for identifier in state.history:
        for item in getattr(blocks[identifier], "fields", ()):
            if not evaluate_condition(item.visible_when, state.answers):
                continue
            if item.validation.optional_when_legacy_missing and item.key not in state.answers:
                continue
            if definition.schema_version == 3 and item.type == "checkbox" and item.key not in state.answers:
                continue  # Do not let the legacy form normalizer invent False.
            raw = item.model_dump(mode="json")
            raw["key"] = item.process_mapping.fact_key or item.key
            raw["required"] = bool(item.required or (item.required_when and evaluate_condition(item.required_when, state.answers)))
            if item.allow_unknown and state.answers.get(item.key) is None:
                raw["required"] = False
            if definition.schema_version == 3 and item.type == "checkbox" and type(state.answers.get(item.key)) is bool:
                # Runtime already enforced presence; the legacy form validator
                # treats required checkbox as consent and rejects explicit No.
                raw["required"] = False
            # Entity pickers were resolved and authorized by the session runtime.
            if item.type.endswith("_picker") and item.key in state.answers:
                raw["options"] = [{"value": state.answers[item.key], "label": str(state.answers[item.key])}]
            fields.append(raw)
    return {"title": definition.title, "version": str(state.revision), "fields": fields}


def processing_facts(definition, state):
    from tickets.request_scenario_processing import FACT_VALUES
    from tickets.request_scenario_conditions import selected_transition, evaluate_condition
    blocks = {block.id: block for block in definition.blocks}
    facts = {}
    def contribute(values):
        for kind, value in values.model_dump(exclude_none=True).items():
            if kind not in facts or FACT_VALUES[kind].index(value) > FACT_VALUES[kind].index(facts[kind]):
                facts[kind] = value
    for identifier in state.history:
        block = blocks[identifier]
        for item in getattr(block, "fields", ()):
            if item.key not in state.answers or not evaluate_condition(item.visible_when, state.answers):
                continue
            value = state.answers[item.key]
            for effect in item.process_mapping.effects:
                if (type(value) is type(effect.value) and value == effect.value) or (isinstance(value, list) and effect.value in value):
                    contribute(effect.facts)
        result = state.results.get(identifier)
        if isinstance(result, dict):
            result = result.get("result") or result.get("status")
        edge = selected_transition(block, state.answers, result)
        if edge and edge.processing_facts:
            contribute(edge.processing_facts)
    return facts


def map_processing(definition, state):
    """Retain only decisions on the validated route; last explicit value wins."""
    from tickets.request_scenario_conditions import selected_transition, condition_evaluation
    config = definition.processing
    selected = {"route": config.defaults.route, "sla_profile": config.defaults.sla_profile}
    sources = {key: {"kind": "default"} for key in selected}
    trace, condition_trace, answers = [], [], {}
    blocks = {block.id: block for block in definition.blocks}
    for offset, identifier in enumerate(state.history):
        block = blocks[identifier]
        for field in getattr(block, "fields", ()):
            if field.key in state.answers:
                answers[field.key] = state.answers[field.key]
        result = state.results.get(identifier)
        if isinstance(result, dict):
            result = result.get("result") or result.get("status")
        edge = selected_transition(block, answers, result)
        expected = state.history[offset + 1] if offset + 1 < len(state.history) else state.current_block_id
        if edge is None or edge.to != expected:
            raise ScenarioInputError({"history": "Retained route no longer matches validated answers"})
        index = next(index for index, item in enumerate(block.transitions) if item is edge)
        for candidate_index, candidate in enumerate(block.transitions):
            condition_trace.append({"block_id": identifier, "transition_index": candidate_index, "to": candidate.to,
                "selected": candidate is edge, "condition_evaluation": condition_evaluation(candidate.when, answers, result)})
        assignments = edge.processing.model_dump(exclude_none=True) if edge.processing else {}
        for key, value in assignments.items():
            selected[key] = value
            sources[key] = {"kind": "transition", "block_id": identifier, "transition_index": index}
        trace.append({"block_id": identifier, "transition_index": index, "to": edge.to,
            "condition": edge.when.model_dump(mode="json") if edge.when else None, "matched": True, "assignments": assignments})
    result = {"assignment_mode": config.assignment_mode, "trace": trace, "condition_trace": condition_trace}
    for kind, items in (("route", config.routes), ("sla_profile", config.sla_profiles)):
        result[kind] = {"key": selected[kind], **items[selected[kind]].model_dump(mode="json"), "source": sources[kind]}
    if "approval_required" in selected:
        result["approval_required"] = selected["approval_required"]
        result["approval_source"] = sources["approval_required"]
    return result


def build_scenario_submission(definition, state, *, session_id, version_id, source_snapshot=None):
    runtime = ScenarioRuntime(definition)
    if state.state != "active" or runtime.blocks[state.current_block_id].kind != "submit_ticket":
        raise ScenarioInputError({"block": "Only the active submit step can create a ticket"})
    # Revalidate retained pages in their traversal order. Unknown/unvisited and
    # conditionally hidden values are never forwarded, even from old storage.
    answers, facts, roles = {}, {}, {}
    for key in state.history:
        block = runtime.blocks[key]
        if block.kind != "form_page":
            continue
        supplied = {item.key: state.answers[item.key] for item in block.fields if item.key in state.answers}
        answers = runtime._page_answers(block, answers, supplied)
        for item in block.fields:
            if item.key not in answers:
                continue
            fact = item.process_mapping.fact_key or item.key
            facts[fact] = deepcopy(answers[item.key])
            roles[fact] = list(item.process_mapping.roles)
    projected = state.__class__(state.current_block_id, state.revision, answers, list(state.history), deepcopy(state.results), state.state)
    summary = project_step(definition, projected)["block"]["answers"]
    description = "\n".join(f"{item['label']}: {item['display_value']}" for item in summary)
    payload = {
        "title": definition.title, "description": (description or definition.title)[:5000],
        "offering_full_code": definition.offering_full_code,
        "request_template_key": definition.process_binding.request_template_key,
        "form_key": definition.process_binding.request_template_key,
        "form_payload": facts,
    }
    snapshot = {
        "session_id": session_id, "version_id": version_id, "scenario_key": definition.scenario_key,
        "answers": answers, "facts": facts, "field_roles": roles, "summary": summary,
        "history": list(state.history),
        "policy_refs": {kind: code for kind, code in definition.process_binding.policy_refs.items()
                        if definition.schema_version != 3 or kind not in {"routing", "sla"}},
        "diagnostics": {key: value for key, value in state.results.items() if key in runtime.blocks and runtime.blocks[key].kind == "diagnostic"},
        "reported_context": deepcopy(state.results.get("_entry_point")),
    }
    if definition.schema_version >= 2:
        snapshot["form_schema"] = derive_scenario_form(definition, projected)
        snapshot["processing_facts"] = processing_facts(definition, projected)
    if definition.schema_version == 3:
        snapshot["map_processing"] = map_processing(definition, projected)
        profile = snapshot["map_processing"]["sla_profile"]
        if source_snapshot is not None and profile["time_basis"] == "business":
            from tickets.request_scenario_processing import validated_scenario_calendar
            frozen = next((item for item in source_snapshot.get("business_calendars", []) if item["id"] == profile["calendar_id"]), None)
            snapshot["map_processing"]["calendar_snapshot"] = validated_scenario_calendar(frozen)
    return payload, snapshot


def augment_scenario_submission(validated, snapshot):
    """Add canonical scenario facts, preserving the form validator's values."""
    if snapshot is None:
        return validated
    result = deepcopy(validated)
    result["submitted_values"] = {**deepcopy(snapshot["facts"]), **result.get("submitted_values", {})}
    context = result.setdefault("template_context", {})
    context["field_roles"] = {**context.get("field_roles", {}), **deepcopy(snapshot["field_roles"])}
    result["summary_rows"] = [
        {"key": item["key"], "label": item["label"], "value": item["display_value"]}
        for item in snapshot["summary"]
    ]
    return result

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
            raw = item.model_dump(mode="json")
            raw["key"] = item.process_mapping.fact_key or item.key
            raw["required"] = bool(item.required or (item.required_when and evaluate_condition(item.required_when, state.answers)))
            if item.allow_unknown and state.answers.get(item.key) is None:
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


def build_scenario_submission(definition, state, *, session_id, version_id):
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
        "policy_refs": dict(definition.process_binding.policy_refs),
        "diagnostics": {key: value for key, value in state.results.items() if key in runtime.blocks and runtime.blocks[key].kind == "diagnostic"},
        "reported_context": deepcopy(state.results.get("_entry_point")),
    }
    if definition.schema_version == 2:
        snapshot["form_schema"] = derive_scenario_form(definition, projected)
        snapshot["processing_facts"] = processing_facts(definition, projected)
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

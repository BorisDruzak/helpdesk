"""Translate a validated, pinned session into trusted canonical create inputs."""
from copy import deepcopy

from tickets.request_scenario_runtime import ScenarioInputError, ScenarioRuntime
from tickets.request_scenario_session import project_step


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
        "diagnostics": {key: value for key, value in state.results.items() if key in runtime.blocks and runtime.blocks[key].kind == "diagnostic"},
    }
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

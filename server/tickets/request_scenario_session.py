"""Safe requester projection; graph execution stays in ScenarioRuntime."""
from tickets.request_scenario_conditions import evaluate_condition


INTERACTIVE = {"form_page", "instruction", "resolution_check", "review"}


def review_display_value(item, value, options=None):
    if value is None:
        return "Не знаю"
    if type(value) is bool:
        return "Да" if value else "Нет"
    if item.type in {"select", "radio", "multi_select", "user_picker", "department_picker", "location_picker", "device_picker", "service_picker"}:
        labels = {option["value"]: option["label"] for option in options} if options is not None else {option.value: option.label for option in item.options}
        values = value if isinstance(value, list) else [value]
        return ", ".join(labels.get(selected, "Недоступное значение") for selected in values)
    return str(value)


def project_step(definition, state):
    blocks = {block.id: block for block in definition.blocks}
    block = blocks[state.current_block_id]
    payload = {"id": block.id, "kind": block.kind, "title": block.title}
    if block.kind == "form_page":
        payload["layout"] = block.layout
        payload["has_dynamic_fields"] = any(item.visible_when is not None or item.required_when is not None for item in block.fields)
        payload["fields"] = []
        for item in block.fields:
            if not evaluate_condition(item.visible_when, state.answers):
                continue
            field = item.model_dump(mode="json", exclude={"process_mapping", "visible_when", "required_when"})
            field["required"] = item.required or (item.required_when is not None and evaluate_condition(item.required_when, state.answers))
            if item.key in state.answers:
                field["value"] = state.answers[item.key]
            payload["fields"].append(field)
    elif block.kind == "instruction":
        payload.update(content=block.content.model_dump(), acknowledgment_required=block.acknowledgment_required)
    elif block.kind == "finish":
        payload["message"] = block.message
    elif block.kind in {"review", "submit_ticket"}:
        payload["answers"] = [
            {"key": item.key, "label": item.label, "type": item.type, "value": state.answers[item.key],
             "display_value": review_display_value(item, state.answers[item.key])}
            for key in state.history for item in getattr(blocks[key], "fields", ())
            if item.key in state.answers and evaluate_condition(item.visible_when, state.answers)
        ]
    targets = [
        {"id": key, "title": blocks[key].title}
        for key in state.history if blocks[key].kind in INTERACTIVE
    ] if state.state == "active" else []
    return {"block": payload, "back_targets": targets}

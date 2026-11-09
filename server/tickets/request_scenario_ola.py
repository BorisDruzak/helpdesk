"""Trusted OLA selection from a retained scenario path, never requester input."""
from copy import deepcopy

from web_api.dto.request_scenario import ScenarioOlaTargets


def select_scenario_ola(definition, state):
    if definition.schema_version != 4:
        return None
    code = definition.process_binding.policy_refs.get("ola")
    selected = {"kind": "policy", "key": code, "source": {"kind": "default"}} if code else None
    for identifier in [*state.history, state.current_block_id]:
        for block in definition.blocks:
            if block.kind != "ola_attachment" or block.attached_to != identifier:
                continue
            source = {"kind": "attachment", "block_id": block.id, "attached_to": identifier}
            if block.targets is not None:
                selected = {"kind": "targets", "targets": block.targets.model_dump(), "source": source}
            elif block.policy_ref:
                selected = {"kind": "policy", "key": block.policy_ref, "source": source}
    terminal = next(block for block in definition.blocks if block.id == state.current_block_id)
    if terminal.kind == "submit_ticket":
        source = {"kind": "terminal", "block_id": terminal.id}
        if terminal.ola_targets is not None:
            selected = {"kind": "targets", "targets": terminal.ola_targets.model_dump(), "source": source}
        elif terminal.ola_policy_ref:
            selected = {"kind": "policy", "key": terminal.ola_policy_ref, "source": source}
    return selected


def apply_scenario_ola(validated, selection):
    """Compose targets into the existing OLA policy/lifecycle, preserving its guards."""
    if not selection or selection["kind"] != "targets":
        return validated
    targets = ScenarioOlaTargets.model_validate(selection["targets"])
    result = deepcopy(validated)
    context = result.setdefault("template_context", {})
    # Keep configured pause/stop/start behavior; only durations are map-owned.
    policy = deepcopy(context.get("ola_policy") or {})
    policy["targets"] = {
        "ack": {priority: targets.ack_minutes for priority in ("P0", "P1", "P2", "P3", "P4")},
        "processing": {priority: targets.processing_minutes for priority in ("P0", "P1", "P2", "P3", "P4")},
    }
    policy["source"] = "request_scenario.ola"
    # A replaced registry identity must not describe the new durations.
    for field in ("code", "policy_code", "ola_policy_code", "id"):
        policy.pop(field, None)
    context["ola_policy"] = policy
    context["scenario_ola"] = deepcopy(selection)
    context.pop("ola_policy_code", None)
    for field in ("policy_refs", "effective_policy_sources", "effective_policy_snapshots"):
        if isinstance(context.get(field), dict):
            context[field].pop("ola", None)
    return result

"""Safely select an executable draft portion for admin-only simulation.

Publication and requester sessions always validate the full immutable graph.
This projection preserves every reachable transition and all strict guarantees.
"""
from dataclasses import asdict
from collections import Counter

from tickets.request_scenario_runtime import ScenarioInputError
from tickets.request_scenario_validation import ScenarioIssue, ScenarioValidationError, require_valid_scenario, validate_scenario
from web_api.dto.request_scenario import ScenarioDefinition, ScenarioDraftDefinition


def simulation_definition(raw, entry_point_key=None):
    draft = ScenarioDraftDefinition.model_validate(raw)
    issues = validate_scenario(draft)
    if not issues:
        return ScenarioDefinition.model_validate(raw), {"limited_scope": False, "excluded_block_ids": [], "issues": []}
    entries = [entry for entry in draft.entry_points if entry.key == entry_point_key]
    if entry_point_key is not None and len(entries) != 1:
        raise ScenarioInputError({"entry_point_key": "Select one unambiguous entrance"})
    start = entries[0].target_block_id if entries else draft.entry_block_id
    counts = Counter(block.id for block in draft.blocks)
    blocks = {block.id: block for block in draft.blocks}
    pending, reached = [start], set()
    while pending:
        identifier = pending.pop()
        if counts[identifier] != 1:
            raise ScenarioValidationError([ScenarioIssue("unknown_or_duplicate_block", "blocks", "Selected route has a missing or ambiguous block")])
        if identifier in reached:
            continue
        reached.add(identifier)
        pending.extend(edge.to for edge in blocks[identifier].transitions)
    selected = draft.model_dump(mode="json")
    selected.update(entry_block_id=start,
        blocks=[block.model_dump(mode="json") for block in draft.blocks if block.id in reached],
        entry_points=[entry.model_dump(mode="json") for entry in entries],
        editor_layout={"positions": {key: point.model_dump(mode="json") for key, point in draft.editor_layout.positions.items() if key in reached or key == "system_start"}})
    definition = ScenarioDefinition.model_validate(selected)
    require_valid_scenario(definition)
    return definition, {"limited_scope": True,
        "excluded_block_ids": [block.id for block in draft.blocks if block.id not in reached],
        "issues": [asdict(issue) for issue in issues]}

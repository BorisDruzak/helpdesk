"""Conservative compatibility for the reviewed, display-only screenshot stage.

Pinned versions keep their block/field identities and uploaded session assets.
Only canonical new publications remove the stage. Neither operation mutates its
input or relaxes an arbitrary required field.
"""
from copy import deepcopy

from web_api.dto.request_scenario import FormPage, ScenarioEditorLayout, ScenarioField, Transition


EVIDENCE_BLOCK = "q_evidence"
EVIDENCE_KEYS = {"evidence_note", "evidence_caption"}
_LABELS = (
    "Скриншот подготовлен или почему его невозможно приложить?",
    "Что видно на снимке или что происходит вместо видимой ошибки?",
)


def _references(value):
    if isinstance(value, dict):
        return any(key in EVIDENCE_KEYS | {EVIDENCE_BLOCK} or _references(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_references(child) for child in value)
    return isinstance(value, str) and value in EVIDENCE_KEYS | {EVIDENCE_BLOCK}


def _remove_stage_position(raw):
    """Only typed editor coordinates are display data, never execution refs."""
    layout = raw.get("editor_layout", {})
    try:
        ScenarioEditorLayout.model_validate(layout)
    except ValueError:
        return False
    layout.get("positions", {}).pop(EVIDENCE_BLOCK, None)
    return True


def _known_stage(raw):
    if not (raw.get("schema_version") == 3 or raw.get("schema_version") == 4 and raw.get("execution_semantics", 3) == 3):
        return False
    candidates = [block for block in raw.get("blocks", []) if block.get("id") == EVIDENCE_BLOCK]
    if len(candidates) != 1:
        return False
    try:
        block = FormPage.model_validate(candidates[0])
    except ValueError:
        return False
    if block.title != "Скриншот или фото ошибки" or block.layout != "group" or len(block.fields) != 2:
        return False
    if block.transitions != [Transition(to="submit")]:
        return False
    for item, key, label, required in zip(block.fields, ("evidence_note", "evidence_caption"), _LABELS, (True, False)):
        # Display copy may vary; every semantic field property must be the
        # reviewed default, including aliases, materials, bounds and mappings.
        expected = ScenarioField(key=key, type="textarea", label=label, required=required,
            help_text=item.help_text, placeholder=item.placeholder)
        if item != expected:
            return False
    targets = [item for item in raw["blocks"] if item.get("id") == "submit"]
    if len(targets) != 1 or targets[0].get("kind") != "submit_ticket":
        return False
    other = deepcopy(raw)
    if not _remove_stage_position(other):
        return False
    other["blocks"] = [item for item in other["blocks"] if item.get("id") != EVIDENCE_BLOCK]
    incoming = 0
    for item in other["blocks"]:
        for edge in item.get("transitions", []):
            if edge.get("to") == EVIDENCE_BLOCK:
                edge["to"] = "submit"
                incoming += 1
    return incoming > 0 and not _references(other)


def effective_definition(definition):
    """Copy a pinned definition, making only the exact legacy stage optional."""
    result = definition.model_copy(deep=True)
    if not _known_stage(definition.model_dump(mode="json")):
        return result
    block = next(item for item in result.blocks if item.id == EVIDENCE_BLOCK)
    block.title = "Скриншот или фото (необязательно)"
    block.fields[0].required = False
    block.fields[0].label = "Комментарий к снимку (необязательно)"
    block.fields[0].help_text = "Можно продолжить без снимка и комментария."
    return result


def without_evidence_stage(raw):
    """Prepare a new publication, aborting on similar or referenced stages."""
    result = deepcopy(raw)
    if not _references(result):
        return result
    if not _known_stage(result):
        raise ValueError("Unrecognized or referenced evidence stage; explicit review is required")
    result["blocks"] = [block for block in result["blocks"] if block["id"] != EVIDENCE_BLOCK]
    _remove_stage_position(result)
    for block in result["blocks"]:
        for edge in block.get("transitions", []):
            if edge.get("to") == EVIDENCE_BLOCK:
                edge["to"] = "submit"
    return result

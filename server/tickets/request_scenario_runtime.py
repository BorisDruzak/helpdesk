"""Canonical, side-effect-free pre-ticket runtime used by simulator and sessions.

No database, HTTP, policy mutation, ticket creation or Endpoint dispatch occurs
here. Callers authorize ownership, pin the immutable version and persist by CAS.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime
import json

from tickets.form_field_values import _field_constraint_error, _normalize_field_value
from tickets.request_scenario_conditions import evaluate_condition, finite_number, leaves, selected_transition, can_request_ticket
from tickets.request_scenario_validation import DIAGNOSTIC_FAILURE_STATUSES, require_valid_scenario


class ScenarioInputError(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("Scenario input is invalid")


class ScenarioConflict(ValueError):
    pass


@dataclass
class RuntimeState:
    current_block_id: str
    revision: int = 1
    answers: dict = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    results: dict = field(default_factory=dict)
    state: str = "active"


class ScenarioRuntime:
    def __init__(self, definition, *, diagnostic_outcomes=None):
        require_valid_scenario(definition)
        # The caller cannot mutate a graph after the safety check.
        self.definition = definition.model_copy(deep=True)
        self.blocks = {block.id: block for block in self.definition.blocks}
        self.diagnostic_outcomes = deepcopy(diagnostic_outcomes)
        for key, status in (self.diagnostic_outcomes or {}).items():
            if key not in self.blocks or self.blocks[key].kind != "diagnostic" or status not in DIAGNOSTIC_FAILURE_STATUSES:
                raise ScenarioInputError({"diagnostic_outcomes": "Only approved diagnostic blocks and failure statuses can be simulated"})

    def initial_state(self, entry_point_key=None):
        entry = next((item for item in self.definition.entry_points if item.key == entry_point_key), None)
        if entry_point_key is not None and entry is None:
            raise ScenarioInputError({"entry_point_key": "Unknown scenario entrance"})
        state = RuntimeState(entry.target_block_id if entry else self.definition.entry_block_id)
        if entry:
            # Server-reported context has no answer/fact/condition authority.
            state.results["_entry_point"] = entry.model_dump(mode="json")
        return self._settle(state)

    def _next(self, block, answers, result=None):
        edge = selected_transition(block, answers, result)
        if edge is None:
            raise ScenarioInputError({"transition": "No valid transition for this result"})
        return edge.to

    def can_request_ticket(self, state):
        return state.state == "active" and can_request_ticket(self.blocks[state.current_block_id], self.blocks, state.answers)

    def _settle(self, state):
        for _ in range(len(self.blocks) + 1):
            block = self.blocks[state.current_block_id]
            if block.kind == "finish":
                state.state = "completed_self_service"
                return state
            if block.kind not in {"decision", "diagnostic"}:
                return state
            result = None
            if block.kind == "diagnostic":
                result = (self.diagnostic_outcomes or {}).get(block.id, "unavailable")
                state.results[block.id] = {"status": result, "reason": "pre_ticket_contract_unavailable"}
                if self.diagnostic_outcomes is not None:
                    state.results[block.id].update(reason="simulated_" + result, simulated=True, operation_created=False, consent_required=block.require_consent)
            state.history.append(block.id)
            state.current_block_id = self._next(block, state.answers, result)
        raise ScenarioInputError({"graph": "Execution limit exceeded"})

    @staticmethod
    def _normalize(field_def, raw):
        kind = field_def.type
        if kind == "number":
            if raw is not None and not finite_number(raw):
                raise ValueError("Enter a finite number")
        elif kind == "checkbox":
            if raw is not None and type(raw) is not bool:
                raise ValueError("Enter a boolean")
        elif kind == "multi_select":
            if raw is not None and (not isinstance(raw, list) or len(raw) > 100 or len(set(raw)) != len(raw)):
                raise ValueError("Enter unique choices")
        elif raw is not None and not isinstance(raw, str):
            raise ValueError("Enter text or a selected entity identifier")
        if raw is None and field_def.allow_unknown:
            return None
        value = _normalize_field_value(field_def.model_dump(), raw)
        if isinstance(value, str) and len(value) > 10000:
            raise ValueError("Text exceeds limit")
        if value and kind == "date":
            date.fromisoformat(value)
        if value and kind == "datetime":
            datetime.fromisoformat(value)
        error = _field_constraint_error(field_def.model_dump(), value)
        if error:
            raise ValueError(error)
        return value

    def _page_answers(self, block, previous, supplied, *, enforce_required=True):
        fields = {item.key: item for item in block.fields}
        if set(supplied) - fields.keys():
            raise ScenarioInputError({"answers": "Only fields from the current page may be submitted"})
        normalized = {key: value for key, value in previous.items() if key not in fields}
        visited = set()
        errors = {}
        def process(key):
            if key in visited: return
            item = fields[key]
            for condition in (item.visible_when, item.required_when):
                for source in leaves(condition):
                    if source.source == "answer" and source.field in fields:
                        process(source.field)
            visited.add(key)
            if not evaluate_condition(item.visible_when, normalized):
                return
            if item.validation.optional_when_legacy_missing and key not in supplied:
                return
            try:
                value = self._normalize(item, supplied.get(key))
            except (ValueError, TypeError):
                errors[key] = "Invalid value or field constraint"
                return
            required = item.required or item.required_when is not None and evaluate_condition(item.required_when, normalized)
            unknown = key in supplied and supplied[key] is None and item.allow_unknown
            empty = value is None or value == "" or value == [] or item.type == "checkbox" and value is False
            if enforce_required and required and empty and not unknown:
                errors[key] = "Field is required"
                return
            if not empty or unknown or item.type == "checkbox":
                normalized[key] = value
        for key in fields: process(key)
        if errors:
            raise ScenarioInputError(errors)
        if len(json.dumps(normalized, ensure_ascii=False).encode("utf-8")) > 65536:
            raise ScenarioInputError({"answers": "Accumulated answers exceed limit"})
        return normalized

    def preview_answers(self, state, request):
        if state.revision != request.revision or state.current_block_id != request.expected_block_id or state.state != "active":
            raise ScenarioConflict("Scenario revision or current block changed")
        block = self.blocks[state.current_block_id]
        if block.kind != "form_page" or request.current_result is not None:
            raise ScenarioInputError({"block": "Only current form answers can be previewed"})
        preview = deepcopy(state)
        preview.answers = self._page_answers(block, state.answers, request.answers, enforce_required=False)
        return preview

    def advance(self, state, request):
        if state.revision != request.revision or state.current_block_id != request.expected_block_id:
            raise ScenarioConflict("Scenario revision or current block changed")
        if state.state != "active":
            raise ScenarioConflict("Session is terminal")
        block = self.blocks[state.current_block_id]
        if block.kind not in {"form_page", "instruction", "resolution_check", "review"}:
            raise ScenarioInputError({"block": "This block cannot be advanced with answers"})
        next_state = deepcopy(state)
        result = request.current_result
        if block.kind == "form_page":
            if result is not None:
                raise ScenarioInputError({"current_result": "A form page has no result confirmation"})
            next_state.answers = self._page_answers(block, state.answers, request.answers)
        else:
            if request.answers:
                raise ScenarioInputError({"answers": "This block does not accept field answers"})
            if block.kind == "resolution_check" and result not in {"yes", "no", "unknown"}:
                raise ScenarioInputError({"current_result": "Explicit yes/no/unknown is required"})
            if block.kind == "instruction":
                if result == "request_ticket":
                    if not self.can_request_ticket(state):
                        raise ScenarioInputError({"current_result": "No explicit ticket request transition is available"})
                elif result not in {None, "acknowledged"} or block.acknowledgment_required and result != "acknowledged":
                    raise ScenarioInputError({"current_result": "Instruction acknowledgment is required"})
            if block.kind == "review" and result is not None:
                raise ScenarioInputError({"current_result": "Review has no result confirmation"})
            if result is not None:
                next_state.results[block.id] = result
        next_state.history.append(block.id)
        next_state.current_block_id = self._next(block, next_state.answers, result)
        next_state.revision += 1
        return self._settle(next_state)

    def back(self, state, target_block_id, *, expected_revision):
        if state.revision != expected_revision or state.state != "active":
            raise ScenarioConflict("Scenario revision or lifecycle changed")
        if target_block_id not in state.history or self.blocks[target_block_id].kind not in {"form_page", "instruction", "resolution_check", "review"}:
            raise ScenarioInputError({"target": "Return is limited to a visited interactive block"})
        result = deepcopy(state)
        index = state.history.index(target_block_id)
        result.history = state.history[:index]
        retained = set(result.history)
        result.results = {key: deepcopy(value) for key, value in state.results.items() if key in retained or key == "_entry_point"}
        retained.add(target_block_id)
        retained_fields = {item.key for key in retained for item in getattr(self.blocks[key], "fields", ())}
        result.answers = {key: value for key, value in state.answers.items() if key in retained_fields}
        result.current_block_id = target_block_id
        result.revision += 1
        return result

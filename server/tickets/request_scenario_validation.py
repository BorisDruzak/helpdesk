"""Pure publish-time scenario DAG/field/condition safety validation."""
from dataclasses import dataclass
from collections import deque
import re

from web_api.dto.request_scenario import Comparison, Membership, Exists
from tickets.request_scenario_conditions import evaluate_condition, finite_number, guarantees_yes, leaves, mutually_exclusive

DIAGNOSTIC_CAPABILITIES = frozenset({"endpoint.context.diagnostic.collect"})
DIAGNOSTIC_FAILURE_STATUSES = ("unavailable", "denied", "timeout", "capability_absent")
AUTHORITY_KEYS = frozenset({"actor_id", "actor_role", "owner_actor_id", "requester_id", "queue_id", "priority", "priority_class", "sla_policy_code", "sla_policy_id", "ola_policy_code", "deadline", "consent_token", "auth_token"})
PRIORITY_TYPES = frozenset({"select", "radio", "number", "checkbox"})


@dataclass(frozen=True)
class ScenarioIssue:
    code: str
    path: str
    message: str


class ScenarioValidationError(ValueError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("Scenario graph is not executable")


def validate_scenario(definition):
    issues = []
    def add(code, path, message):
        issues.append(ScenarioIssue(code, path, message))
    blocks = {}
    fields = {}
    locations = {}
    dependencies = {}
    fact_keys = set()
    for block in definition.blocks:
        path = f"blocks.{block.id}"
        if block.id in blocks:
            add("duplicate_block", path, "Block identifier is duplicated")
        blocks[block.id] = block
        if block.kind == "form_page":
            group_titles = {}
            if block.layout == "single" and len(block.fields) != 1:
                add("invalid_layout", path, "Single-question layout requires one field")
            for field in block.fields:
                fp = f"{path}.fields.{field.key}"
                if field.group_title is not None:
                    if not field.group or not field.group_title.strip():
                        add("invalid_group", fp, "Named section requires a group and nonblank title")
                    elif field.group in group_titles and group_titles[field.group] != field.group_title:
                        add("invalid_group", fp, "Fields in one section must use the same title")
                    else:
                        group_titles[field.group] = field.group_title
                if field.key in fields:
                    add("duplicate_field", fp, "Field identifier is duplicated")
                fields[field.key] = field
                locations[field.key] = block.id
                dependencies[field.key] = set()
                if field.key in AUTHORITY_KEYS or field.process_mapping.fact_key in AUTHORITY_KEYS:
                    add("unsafe_fact_key", fp, "Field cannot supply identity or computed policy authority")
                fact = field.process_mapping.fact_key or field.key
                if fact in fact_keys:
                    add("duplicate_fact_key", fp, "Two fields cannot overwrite the same fact")
                fact_keys.add(fact)
                if any(role.startswith("priority_") for role in field.process_mapping.roles) and field.type not in PRIORITY_TYPES:
                    add("incompatible_role", fp, "Priority roles require a choice, number or checkbox")
                if "approval_subject" in field.process_mapping.roles and field.type not in {"user_picker", "department_picker"}:
                    add("incompatible_role", fp, "Approval subject requires a verified entity picker")
                bounds = field.validation
                if any(value is not None and not finite_number(value) for value in (bounds.min_value, bounds.max_value)):
                    add("invalid_validation", fp, "Numeric bounds must be finite wire-safe numbers")
                if field.type != "number" and (bounds.min_value is not None or bounds.max_value is not None):
                    add("invalid_validation", fp, "Numeric bounds require a number field")
                if field.type in {"number", "checkbox", "multi_select"} and (bounds.min_length is not None or bounds.max_length is not None):
                    add("invalid_validation", fp, "Length bounds require a string field")
                if field.options and field.type not in {"select", "radio", "multi_select"}:
                    add("invalid_options", fp, "Options require a choice field")
        if block.kind == "diagnostic" and block.capability not in DIAGNOSTIC_CAPABILITIES:
            add("unknown_capability", path, "Pre-ticket capability is not supported")
        if block.kind == "instruction" and block.content.format == "markdown":
            if re.search(r"<[A-Za-z!/]", block.content.body) or re.search(r"\]\(\s*(?:javascript|data|file):", block.content.body, re.I):
                add("unsafe_instruction", path, "Instructions cannot contain HTML or executable links")

    if definition.entry_block_id not in blocks:
        add("unknown_entry", "entry_block_id", "Entry block does not exist")
    adjacency = {key: [] for key in blocks}
    parents = {key: set() for key in blocks}
    for block in blocks.values():
        path = f"blocks.{block.id}.transitions"
        terminal = block.kind in {"finish", "submit_ticket"}
        if terminal and block.transitions:
            add("terminal_outgoing", path, "A terminal cannot execute another block")
        conditional = [edge for edge in block.transitions if edge.when is not None]
        fallback = [edge for edge in block.transitions if edge.when is None]
        # An empty answer set cannot prove coverage for real user answers.
        result_only = [edge for edge in conditional if all(leaf.source == "current_result" for leaf in leaves(edge.when))]
        exhaustive = block.kind == "resolution_check" and all(
            any(evaluate_condition(edge.when, {}, result) for edge in result_only) for result in ("yes", "no", "unknown"))
        if not terminal and (len(fallback) != 1 and not (len(fallback) == 0 and exhaustive)):
            add("missing_fallback", path, "Every possible result needs an exit and explicit fallback")
        if fallback and block.transitions[-1].when is not None:
            add("invalid_fallback_order", path, "Fallback must follow conditional branches")
        def exclusive(a, b):
            # Disjoint expected membership sets may both match a multi-select answer.
            if any(leaf.source == "answer" and fields.get(leaf.field) and fields[leaf.field].type == "multi_select" for leaf in leaves(a.when)):
                return False
            return mutually_exclusive(a.when, b.when)
        overlap = any(not exclusive(a, b) for i, a in enumerate(conditional) for b in conditional[i + 1:])
        priorities = [edge.priority for edge in conditional]
        if (overlap and any(value is None for value in priorities)) or len([p for p in priorities if p is not None]) != len({p for p in priorities if p is not None}):
            add("ambiguous_precedence", path, "Overlapping branches require distinct explicit priorities")
        for edge in block.transitions:
            if edge.to not in blocks:
                add("unknown_target", path, "Transition target does not exist")
            else:
                adjacency[block.id].append(edge.to)
                parents[edge.to].add(block.id)

    colors = {}
    def visit(key):
        if colors.get(key) == 1:
            add("cycle", f"blocks.{key}", "Automatic graph cycles are forbidden")
            return
        if colors.get(key) == 2:
            return
        colors[key] = 1
        for child in adjacency[key]: visit(child)
        colors[key] = 2
    for key in blocks: visit(key)

    def reachable(start, edges):
        seen, pending = set(), [start]
        while pending:
            key = pending.pop()
            if key in seen or key not in edges: continue
            seen.add(key)
            pending.extend(edges[key])
        return seen
    reached = reachable(definition.entry_block_id, adjacency)
    for key in blocks.keys() - reached:
        add("unreachable_block", f"blocks.{key}", "Block cannot be reached from entry")
    unconfirmed = {key: [edge.to for edge in block.transitions if not (block.kind == "resolution_check" and guarantees_yes(edge.when))] for key, block in blocks.items()}
    unconfirmed_reached = reachable(definition.entry_block_id, unconfirmed)
    for key in unconfirmed_reached:
        if blocks[key].kind == "finish":
            add("unconfirmed_finish", f"blocks.{key}", "Self-resolution requires an explicit positive result check")

    def check_condition(condition, block, path, field_key=None):
        ancestors = reachable(block.id, parents)
        for leaf in leaves(condition):
            if leaf.source == "answer":
                field = fields.get(leaf.field)
                if field is None:
                    add("unknown_field", path, "Condition references an unknown field")
                    continue
                if locations[leaf.field] not in ancestors:
                    add("future_field_reference", path, "Condition depends on a future or unrelated page")
                if field_key:
                    dependencies[field_key].add(leaf.field)
                kind = field.type
                valid = lambda value: value is None or (finite_number(value) if kind == "number" else type(value) is bool if kind == "checkbox" else isinstance(value, str))
                if isinstance(leaf, Comparison) and leaf.op in {"gt", "gte", "lt", "lte"} and (kind != "number" or not finite_number(leaf.value)):
                    add("incompatible_condition", path, "Ordering requires numeric values")
                elif not isinstance(leaf, Exists):
                    values = leaf.value if isinstance(leaf, Membership) else [leaf.value]
                    if not all(valid(value) for value in values) or kind == "multi_select" and isinstance(leaf, Comparison):
                        add("incompatible_condition", path, "Condition value is incompatible with its source field")
                    elif kind in {"select", "radio", "multi_select"} and any(value is not None and value not in {opt.value for opt in field.options} for value in values):
                        add("incompatible_condition", path, "Condition uses an undeclared option")
            else:
                allowed = {"resolution_check": ("yes", "no", "unknown"), "instruction": ("acknowledged",), "diagnostic": DIAGNOSTIC_FAILURE_STATUSES}.get(block.kind, ())
                if field_key or not allowed or isinstance(leaf, Comparison) and leaf.op not in {"eq", "neq"}:
                    add("incompatible_condition", path, "Current result is not available at this condition")
                elif not isinstance(leaf, Exists):
                    values = leaf.value if isinstance(leaf, Membership) else [leaf.value]
                    if not all(value in allowed for value in values):
                        add("incompatible_condition", path, "Unknown result for this block type")
    for block in blocks.values():
        for edge in block.transitions: check_condition(edge.when, block, f"blocks.{block.id}.transitions")
        if block.kind == "form_page":
            for field in block.fields:
                for condition in (field.visible_when, field.required_when):
                    check_condition(condition, block, f"blocks.{block.id}.fields.{field.key}", field.key)
    # Kahn traversal avoids Python recursion for long, otherwise valid dependencies.
    indegree = {key: len(sources & dependencies.keys()) for key, sources in dependencies.items()}
    dependents = {key: [] for key in dependencies}
    for key, sources in dependencies.items():
        for source in sources & dependencies.keys(): dependents[source].append(key)
    ready = deque(key for key, degree in indegree.items() if degree == 0)
    while ready:
        source = ready.popleft()
        for key in dependents[source]:
            indegree[key] -= 1
            if indegree[key] == 0: ready.append(key)
    for key, degree in indegree.items():
        if degree:
            add("field_dependency_cycle", f"fields.{key}", "Field visibility/required dependency is cyclic")
    return issues


def require_valid_scenario(definition):
    issues = validate_scenario(definition)
    if issues:
        raise ScenarioValidationError(issues)

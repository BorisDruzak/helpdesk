"""Pure publish-time scenario DAG/field/condition safety validation."""
from dataclasses import dataclass
from collections import deque
import re

from web_api.dto.request_scenario import Comparison, Membership, Exists
from tickets.request_scenario_conditions import evaluate_condition, finite_number, guarantees_yes, leaves, mutually_exclusive, explicit_ticket_request

DIAGNOSTIC_CAPABILITIES = frozenset({"endpoint.context.diagnostic.collect"})
DIAGNOSTIC_FAILURE_STATUSES = ("unavailable", "denied", "timeout", "capability_absent")
AUTHORITY_KEYS = frozenset({"actor_id", "actor_role", "owner_actor_id", "requester_id", "queue_id", "priority", "priority_class", "sla_policy_code", "sla_policy_id", "ola_policy_code", "deadline", "consent_token", "auth_token"})
MODIFIER_KINDS = frozenset({"sla_attachment", "routing_attachment"})
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
    entrance_keys = {entry.key for entry in definition.entry_points}
    if len(definition.entry_points) + len(definition.editor_layout.pending_entrances) > 64:
        add("entry_limit", "editor_layout.pending_entrances", "Допускается не больше 64 входов из каталога.")
    for index, entry in enumerate(definition.editor_layout.pending_entrances):
        path = f"editor_layout.pending_entrances.{index}"
        if entry.key in entrance_keys:
            add("duplicate_entry", path, "Идентификатор входа повторяется.")
        entrance_keys.add(entry.key)
        add("unconnected_catalog_entry", path, f"Соедините вход «{entry.title}» с первым блоком или удалите его.")
    if definition.schema_version == 3 or definition.schema_version == 4 and definition.processing is not None:
        config = definition.processing
        if config is None:
            add("processing_missing", "processing", "Настройте направления и сроки обработки карты.")
        else:
            for kind, choices in (("route", config.routes), ("sla_profile", config.sla_profiles)):
                value = getattr(config.defaults, kind)
                if (definition.schema_version == 3 or value) and value not in choices:
                    add("processing_default_missing", f"processing.defaults.{kind}", "Выберите существующее значение по умолчанию.")
                for block in definition.blocks:
                    for index, edge in enumerate(block.transitions):
                        value = getattr(edge.processing, kind, None)
                        if value is not None and value not in choices:
                            add("processing_reference_unknown", f"blocks.{block.id}.transitions.{index}.processing.{kind}", "Результат ветки ссылается на отсутствующую настройку карты.")
            for block in definition.blocks:
                if block.kind in {"sla", "sla_attachment", "submit_ticket"} and block.sla_profile is not None and block.sla_profile not in config.sla_profiles:
                    add("processing_reference_unknown", f"blocks.{block.id}.sla_profile", "Unknown SLA profile")
            for block in definition.blocks:
                if block.kind in {"routing_attachment", "submit_ticket"} and block.route is not None and block.route not in config.routes:
                    add("processing_reference_unknown", f"blocks.{block.id}.route", "Unknown map route")
            for key, profile in config.sla_profiles.items():
                for duration in ("first_response_minutes", "resolution_minutes"):
                    if getattr(profile, duration) < 1:
                        add("processing_duration_missing", f"processing.sla_profiles.{key}.{duration}", "Укажите положительный срок в минутах.")
                if profile.time_basis == "business" and profile.calendar_id is None:
                    add("processing_calendar_missing", f"processing.sla_profiles.{key}.calendar_id", "Для рабочих сроков выберите рабочий календарь.")
            for key, route in config.routes.items():
                if not route.queue_code.strip():
                    add("processing_queue_missing", f"processing.routes.{key}.queue_code", "Выберите действующую очередь.")
    from tickets.request_scenario_assets import rich_asset_nodes
    for attrs, allowed in rich_asset_nodes(definition):
        if attrs["asset_id"] not in allowed:
            add("rich_asset_missing", "blocks", "Rich images must reference an attached authorized asset")
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
                if field.process_mapping.effects:
                    values = [option.value for option in field.options] if field.type in {"select", "radio", "multi_select"} else [True, False] if field.type == "checkbox" else []
                    if field.allow_unknown:
                        values.append(None)
                    used = set()
                    for effect in field.process_mapping.effects:
                        signature = (type(effect.value).__name__, str(effect.value))
                        if not any(type(value) is type(effect.value) and value == effect.value for value in values) or signature in used:
                            add("invalid_processing_effect", fp, "Влияние на обработку должно соответствовать существующему варианту ответа.")
                        used.add(signature)
        if block.kind == "diagnostic" and block.capability not in DIAGNOSTIC_CAPABILITIES:
            add("unknown_capability", path, "Pre-ticket capability is not supported")
        if block.kind == "instruction" and block.content.format == "markdown":
            if re.search(r"<[A-Za-z!/]", block.content.body) or re.search(r"\]\(\s*(?:javascript|data|file):", block.content.body, re.I):
                add("unsafe_instruction", path, "Instructions cannot contain HTML or executable links")

    attachment_targets = set()
    for block in definition.blocks:
        if block.kind not in MODIFIER_KINDS:
            continue
        path = f"blocks.{block.id}.attached_to"
        target = blocks.get(block.attached_to)
        if target is None or target.kind in MODIFIER_KINDS:
            add("attachment_target_invalid", path, "Attach settings to an existing ordinary block")
        elif (block.kind, block.attached_to) in attachment_targets:
            add("duplicate_attachment", path, "Only one setting of each kind may attach to a block")
        attachment_targets.add((block.kind, block.attached_to))
    if definition.entry_block_id in blocks and blocks[definition.entry_block_id].kind in MODIFIER_KINDS:
        add("modifier_flow_target", "entry_block_id", "A setting cannot be a flow entrance")
    if definition.entry_block_id not in blocks:
        add("unknown_entry", "entry_block_id", "Entry block does not exist")
    if (definition.execution_semantics if definition.schema_version == 4 else definition.schema_version) == 2 and (not definition.entry_points or not any(
        entry.enabled and entry.target_block_id == definition.entry_block_id for entry in definition.entry_points
    )):
        add("catalog_entry_required", "entry_points", "Соедините «Начало» с первым шагом: услуге нужен вход из каталога.")
    entries = [definition.entry_block_id]
    entry_keys = set()
    for entry in definition.entry_points:
        path = f"entry_points.{entry.key}"
        if entry.key in entry_keys:
            add("duplicate_entry", path, "Entrance identifier is duplicated")
        entry_keys.add(entry.key)
        if entry.target_block_id not in blocks:
            add("unknown_entry", path, "Entrance target does not exist")
        if entry.target_block_id in blocks and blocks[entry.target_block_id].kind in MODIFIER_KINDS:
            add("modifier_flow_target", path + ".target_block_id", "A setting cannot be a flow entrance")
        entries.append(entry.target_block_id)
    for key in definition.editor_layout.positions:
        if key not in blocks and key != "system_start":
            add("unknown_layout_block", f"editor_layout.positions.{key}", "Layout refers to a missing block")
    adjacency = {key: [] for key in blocks}
    parents = {key: set() for key in blocks}
    for block in blocks.values():
        path = f"blocks.{block.id}.transitions"
        if definition.schema_version == 4:
            for profile_field, policy_field, kinds, label in (
                ("sla_profile", "policy_ref", {"sla_attachment"}, "SLA"),
                ("route", "routing_policy_ref" if block.kind == "submit_ticket" else "policy_ref", {"routing_attachment", "submit_ticket"}, "routing"),
            ):
                if block.kind not in kinds:
                    continue
                profile, policy = getattr(block, profile_field), getattr(block, policy_field)
                if profile and policy:
                    add("invalid_processing_source", f"blocks.{block.id}.{profile_field}", f"Choose one {label} map value or published policy")
                if policy and definition.processing is not None:
                    add("invalid_processing_source", f"blocks.{block.id}.{policy_field}", f"Map-owned {label} cannot select a registry policy")
                if profile and definition.processing is None:
                    add("processing_reference_unknown", f"blocks.{block.id}.{profile_field}", f"{label} value requires map processing")
        if block.kind in MODIFIER_KINDS:
            continue
        terminal = block.kind in {"finish", "submit_ticket"}
        if terminal and block.transitions:
            add("terminal_outgoing", path, "A terminal cannot execute another block")
        buttons = definition.schema_version == 4 and block.transition_mode == "buttons"
        if definition.schema_version == 4:
            interactive = block.kind in {"form_page", "instruction", "review", "navigation"}
            if block.kind == "navigation" and not buttons or buttons and not interactive:
                add("invalid_transition_mode", path, "Button mode requires an interactive block")
            if buttons and block.kind == "instruction":
                for edge in block.transitions:
                    for leaf in leaves(edge.when):
                        values = getattr(leaf, "value", [])
                        values = values if isinstance(values, list) else [values]
                        if leaf.source == "current_result" and any(value != "acknowledged" for value in values):
                            add("invalid_button_result", path, "Instruction buttons support acknowledgment only")
            if buttons:
                keys = [edge.button.key for edge in block.transitions if edge.button]
                if not 1 <= len(block.transitions) <= 10 or len(keys) != len(block.transitions) or len(keys) != len(set(keys)):
                    add("invalid_buttons", path, "Provide 1–10 uniquely keyed buttons")
            elif any(edge.button is not None for edge in block.transitions):
                add("invalid_buttons", path, "Automatic transitions cannot have buttons")
            if block.kind == "sla" and (len(block.transitions) != 1 or block.transitions[0].when is not None or block.sla_profile and block.policy_ref):
                add("invalid_sla", path, "SLA requires one unconditional continuation and at most one profile or policy")
            if block.kind == "submit_ticket" and block.sla_profile and block.policy_ref:
                add("invalid_sla", f"blocks.{block.id}.sla_profile", "Choose one final SLA profile or policy")
            if block.kind in {"sla", "submit_ticket"} and block.policy_ref and definition.processing is not None:
                add("invalid_sla", f"blocks.{block.id}.policy_ref", "A map-owned SLA cannot select a registry policy")
            if block.kind in {"sla", "sla_attachment", "submit_ticket"} and block.sla_profile and definition.processing is None:
                add("processing_reference_unknown", f"blocks.{block.id}.sla_profile", "SLA profile requires map processing")
        conditional = [edge for edge in block.transitions if edge.when is not None]
        fallback = [edge for edge in block.transitions if edge.when is None]
        # An empty answer set cannot prove coverage for real user answers.
        result_only = [edge for edge in conditional if all(leaf.source == "current_result" for leaf in leaves(edge.when))]
        exhaustive = block.kind == "resolution_check" and all(
            any(evaluate_condition(edge.when, {}, result) for edge in result_only) for result in ("yes", "no", "unknown"))
        if not terminal and not buttons and (len(fallback) != 1 and not (len(fallback) == 0 and exhaustive)):
            add("missing_fallback", path, "Every possible result needs an exit and explicit fallback")
        if not buttons and fallback and block.transitions[-1].when is not None:
            add("invalid_fallback_order", path, "Fallback must follow conditional branches")
        def exclusive(a, b):
            # Disjoint expected membership sets may both match a multi-select answer.
            if any(leaf.source == "answer" and fields.get(leaf.field) and fields[leaf.field].type == "multi_select" for leaf in leaves(a.when)):
                return False
            return mutually_exclusive(a.when, b.when)
        overlap = any(not exclusive(a, b) for i, a in enumerate(conditional) for b in conditional[i + 1:])
        priorities = [edge.priority for edge in conditional]
        if not buttons and ((overlap and any(value is None for value in priorities)) or len([p for p in priorities if p is not None]) != len({p for p in priorities if p is not None})):
            add("ambiguous_precedence", path, "Overlapping branches require distinct explicit priorities")
        for edge in block.transitions:
            ticket_result = False
            if block.kind == "instruction" and edge.when is not None:
                ticket_result = any(
                    leaf.source == "current_result" and (
                        "request_ticket" in leaf.value if isinstance(leaf, Membership)
                        else getattr(leaf, "value", None) == "request_ticket")
                    for leaf in leaves(edge.when))
            if ticket_result:
                if not explicit_ticket_request(edge.when):
                    add("invalid_ticket_request_condition", path, "A ticket request requires an explicit current-result equality")
                if edge.to in blocks and blocks[edge.to].kind != "review":
                    add("invalid_ticket_request_target", path, "A ticket request must lead to a review block")
            if edge.to not in blocks:
                add("unknown_target", path, "Transition target does not exist")
            elif blocks[edge.to].kind in MODIFIER_KINDS:
                add("modifier_flow_target", path, "Flow transitions cannot enter settings")
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
    reached = set().union(*(reachable(entry, adjacency) for entry in entries))
    for key in {key for key, block in blocks.items() if block.kind not in MODIFIER_KINDS} - reached:
        add("unreachable_block", f"blocks.{key}", "Block cannot be reached from entry")
    unconfirmed = {key: [edge.to for edge in block.transitions if not (block.kind == "resolution_check" and guarantees_yes(edge.when))] for key, block in blocks.items()}
    unconfirmed_reached = set().union(*(reachable(entry, unconfirmed) for entry in entries))
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
                allowed = {"resolution_check": ("yes", "no", "unknown"), "instruction": ("acknowledged", "request_ticket"), "diagnostic": DIAGNOSTIC_FAILURE_STATUSES}.get(block.kind, ())
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

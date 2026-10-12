"""Bounded typed conditions shared by graph validation and execution."""
import math

from web_api.dto.request_scenario import AllAny, Comparison, Exists, Membership, Negation


def leaves(condition):
    if condition is None:
        return
    if isinstance(condition, AllAny):
        for child in condition.conditions:
            yield from leaves(child)
    elif isinstance(condition, Negation):
        yield from leaves(condition.condition)
    else:
        yield condition


def same_value(left, right):
    if finite_number(left) and finite_number(right):
        return left == right
    if type(left) in (int, float) or type(right) in (int, float):
        return False
    return type(left) is type(right) and left == right


def finite_number(value):
    # JS wire precision and conversion safety: never float() an unbounded integer.
    return type(value) in (int, float) and (type(value) is int or math.isfinite(value)) and abs(value) <= 9007199254740991


def evaluate_condition(condition, answers, current_result=None):
    if condition is None:
        return True
    if isinstance(condition, AllAny):
        values = (evaluate_condition(child, answers, current_result) for child in condition.conditions)
        return all(values) if condition.op == "and" else any(values)
    if isinstance(condition, Negation):
        return not evaluate_condition(condition.condition, answers, current_result)
    present = condition.field in answers if condition.source == "answer" else current_result is not None
    value = answers.get(condition.field) if condition.source == "answer" else current_result
    if isinstance(condition, Exists):
        return present and value is not None and value != "" and value != []
    if not present:
        return False
    if isinstance(condition, Membership):
        candidates = value if isinstance(value, list) else [value]
        return any(same_value(candidate, expected) for candidate in candidates for expected in condition.value)
    if condition.op in {"eq", "neq"}:
        matches = same_value(value, condition.value)
        return matches if condition.op == "eq" else not matches
    if not finite_number(value) or not finite_number(condition.value):
        return False
    return {"gt": lambda: value > condition.value, "gte": lambda: value >= condition.value,
            "lt": lambda: value < condition.value, "lte": lambda: value <= condition.value}[condition.op]()


def explicit_ticket_request(condition):
    """Only a declared instruction result grants the escape action."""
    return isinstance(condition, Comparison) and condition.source == "current_result" and condition.op == "eq" and condition.value == "request_ticket"


def selected_transition(block, answers, result=None):
    conditional = sorted((edge for edge in block.transitions if edge.when is not None),
                         key=lambda edge: edge.priority if edge.priority is not None else 10001)
    return next((edge for edge in conditional if evaluate_condition(edge.when, answers, result)),
                next((edge for edge in block.transitions if edge.when is None), None))


def can_request_ticket(block, blocks, answers):
    if block.kind != "instruction":
        return False
    edge = selected_transition(block, answers, "request_ticket")
    return bool(edge and explicit_ticket_request(edge.when) and blocks.get(edge.to) and blocks[edge.to].kind == "review")


def guarantees_yes(condition):
    """Conservative proof for paths allowed to finish without a ticket."""
    if isinstance(condition, AllAny):
        checks = [guarantees_yes(child) for child in condition.conditions]
        return any(checks) if condition.op == "and" else all(checks)
    return (isinstance(condition, Comparison) and condition.source == "current_result" and condition.op == "eq" and condition.value == "yes") or (
        isinstance(condition, Membership) and condition.source == "current_result" and condition.value == ["yes"])


def mutually_exclusive(left, right):
    if not isinstance(left, (Comparison, Membership)) or not isinstance(right, (Comparison, Membership)):
        return False
    if left.source != right.source or left.field != right.field:
        return False
    if isinstance(left, Comparison) and left.op != "eq" or isinstance(right, Comparison) and right.op != "eq":
        return False
    a = left.value if isinstance(left, Membership) else [left.value]
    b = right.value if isinstance(right, Membership) else [right.value]
    return not any(same_value(x, y) for x in a for y in b)

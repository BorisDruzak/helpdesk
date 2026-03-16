"""
Этап 7: Безопасная оценка if_expr и подстановка params_template для playbook steps.

- if_expr: только доступ к context и prev_steps, без exec/eval произвольного кода.
- params_template: подстановка {{ context.key }}, {{ steps.step_key.output.key }} и т.п.
"""
from typing import Any, Dict, Optional
import ast
import re
import logging

log = logging.getLogger(__name__)

# Разрешённые имена в if_expr (только context и prev_steps)
_ALLOWED_NAMES = frozenset({"context", "prev_steps"})


def _safe_eval_node(node: ast.AST, namespace: Dict[str, Any]) -> Any:
    """
    Рекурсивная оценка AST-узла с разрешённым namespace.
    Разрешены: Constant, Name (только context/prev_steps), Subscript, Attribute (без _),
    Compare, BoolOp (And/Or), UnaryOp(Not), Call только для .get с константными аргументами.
    """
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in _ALLOWED_NAMES:
            raise ValueError(f"Disallowed name in if_expr: {node.id!r}")
        return namespace[node.id]
    if isinstance(node, ast.Attribute):
        if node.attr.startswith("_"):
            raise ValueError(f"Disallowed attribute: {node.attr!r}")
        val = _safe_eval_node(node.value, namespace)
        return getattr(val, node.attr)
    if isinstance(node, ast.Subscript):
        val = _safe_eval_node(node.value, namespace)
        slice_val = getattr(node.slice, "value", node.slice)  # Python 3.8 Index.value; 3.9 slice
        if isinstance(slice_val, ast.Constant):
            return val[slice_val.value]
        if hasattr(ast, "Str") and isinstance(slice_val, ast.Str):  # Python 3.7
            return val[slice_val.s]
        raise ValueError("Subscript index must be constant")
    if isinstance(node, ast.Compare):
        left = _safe_eval_node(node.left, namespace)
        for op, right in zip(node.ops, node.comparators):
            right_val = _safe_eval_node(right, namespace)
            if isinstance(op, ast.Eq):
                if left != right_val:
                    return False
            elif isinstance(op, ast.NotEq):
                if left == right_val:
                    return False
            elif isinstance(op, ast.In):
                if left not in right_val:
                    return False
            elif isinstance(op, ast.NotIn):
                if left in right_val:
                    return False
            else:
                raise ValueError(f"Disallowed comparison: {type(op).__name__}")
            left = right_val
        return True
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_safe_eval_node(v, namespace) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_safe_eval_node(v, namespace) for v in node.values)
        raise ValueError("Unsupported BoolOp")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _safe_eval_node(node.operand, namespace)
    if isinstance(node, ast.Call):
        # Разрешаем только .get(x) или .get(x, default)
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "get":
            raise ValueError("Only .get() calls allowed in if_expr")
        obj = _safe_eval_node(func.value, namespace)
        if not node.args or len(node.args) > 2:
            raise ValueError(".get() must have 1 or 2 arguments")
        key = _safe_eval_node(node.args[0], namespace)
        default = _safe_eval_node(node.args[1], namespace) if len(node.args) == 2 else None
        if hasattr(obj, "get"):
            return obj.get(key, default)
        raise ValueError("get() only on mapping types")
    raise ValueError(f"Disallowed node type in if_expr: {type(node).__name__}")


def evaluate_if_expr(
    if_expr: Optional[str],
    context: Dict[str, Any],
    prev_steps: Dict[str, Dict[str, Any]],
) -> bool:
    """
    Безопасная оценка условия шага. Только context и prev_steps в namespace.

    - Пустое/None выражение → True (шаг выполняется).
    - При ошибке парсинга/оценки → False (шаг пропускается, логируем предупреждение).

    prev_steps: { step_key: { "output": {...}, "error": {...}, "status": "success"|"failed" } }
    """
    if not if_expr or not (s := if_expr.strip()):
        return True
    namespace = {"context": context or {}, "prev_steps": prev_steps or {}}
    try:
        tree = ast.parse(s, mode="eval")
        if not isinstance(tree.body, (ast.Compare, ast.BoolOp, ast.UnaryOp, ast.Name, ast.Constant, ast.Call, ast.Attribute, ast.Subscript)):
            log.warning("[playbook_step_eval] if_expr must evaluate to bool-like expression")
            return False
        result = _safe_eval_node(tree.body, namespace)
        return bool(result)
    except (ValueError, SyntaxError, KeyError, TypeError, AttributeError) as e:
        log.warning("[playbook_step_eval] if_expr evaluation failed: %s expr=%r", e, if_expr[:200])
        return False


def _flatten_for_template(context: Dict[str, Any], prev_steps: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Строит плоский словарь для подстановки: context.*, steps.<key>.output.*, steps.<key>.error.*, steps.<key>.status."""
    out = {}
    for k, v in (context or {}).items():
        out[f"context.{k}"] = v
    for step_key, data in (prev_steps or {}).items():
        prefix = f"steps.{step_key}."
        for sub in ("output", "error", "status"):
            val = (data or {}).get(sub)
            if val is not None and sub != "status":
                if isinstance(val, dict):
                    for k, v in val.items():
                        out[f"{prefix}{sub}.{k}"] = v
                else:
                    out[f"{prefix}{sub}"] = val
            elif sub == "status":
                out[f"{prefix}status"] = val
    return out


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def resolve_params_template(
    params_template_json: Optional[Dict[str, Any]],
    context: Dict[str, Any],
    prev_steps: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Подставляет в params_template значения из context и prev_steps.

    - params_template_json: как в playbook_step (dict или null).
    - Поддержка плейсхолдеров в строках: {{ context.key }}, {{ steps.step_key.output.field }}.
    - Ключи в flat: context.<key>, steps.<step_key>.output.<key>, steps.<step_key>.error.<key>, steps.<step_key>.status.
    """
    if not params_template_json or not isinstance(params_template_json, dict):
        return {}

    flat = _flatten_for_template(context, prev_steps)

    def replace_string(s: str) -> str:
        def repl(match: re.Match) -> str:
            key = match.group(1).strip()
            if key in flat:
                v = flat[key]
                return str(v) if v is not None else ""
            return match.group(0)

        return _PLACEHOLDER_RE.sub(repl, s)

    def recurse(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: recurse(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [recurse(v) for v in obj]
        if isinstance(obj, str):
            return replace_string(obj)
        return obj

    return recurse(dict(params_template_json))

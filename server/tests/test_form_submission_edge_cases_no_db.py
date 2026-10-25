from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pytest

from tickets.form_catalog import validate_form_pack_schema, validate_form_submission

pytestmark = pytest.mark.no_db


def pack_for(*fields):
    return {"pack_key": "edge_cases", "version": "1", "title": "Edge cases",
            "forms": [{"key": "probe", "title": "Probe", "fields": list(fields)}]}


def field(key="amount", kind="number", **kwargs):
    return {"key": key, "label": key, "type": kind, **kwargs}


def submit(pack, **values):
    return validate_form_submission(pack, form_key="probe", raw_values=values)


@pytest.mark.parametrize("value", [0, "0", 0.0, 1, -1])
def test_required_number_accepts_zero(value):
    assert submit(pack_for(field(required=True)), amount=value)["submitted_values"]["amount"] == float(value)


@pytest.mark.parametrize("value", [None, ""])
def test_required_number_rejects_missing(value):
    with pytest.raises(ValueError, match="Поле обязательно"):
        submit(pack_for(field(required=True)), amount=value)


def test_number_min_still_rejects_zero():
    with pytest.raises(ValueError, match="Минимальное значение"):
        submit(pack_for(field(required=True, validation={"min": 1})), amount=0)


@pytest.mark.parametrize("raw, expected", [(True, True), (False, False), ("true", True), ("false", False),
    ("True", True), ("False", False), ("1", True), ("0", False), ("yes", True), ("no", False), (None, False)])
def test_checkbox_false_string_is_not_true(raw, expected):
    assert submit(pack_for(field("flag", "checkbox")), flag=raw)["submitted_values"]["flag"] is expected


@pytest.mark.parametrize("raw", [False, "false", "False", "0", "no", None])
def test_required_checkbox_false_is_rejected(raw):
    with pytest.raises(ValueError):
        submit(pack_for(field("flag", "checkbox", required=True)), flag=raw)


@pytest.mark.parametrize("raw", [[], {}, "unexpected", 1, 0])
def test_checkbox_invalid_type_rejected(raw):
    with pytest.raises(ValueError):
        submit(pack_for(field("flag", "checkbox")), flag=raw)


@pytest.mark.parametrize("operator", ["equals", "in"])
@pytest.mark.parametrize("condition, value", [(True, True), (False, False), ("True", True),
    ("False", False), ("true", True), ("false", False)])
def test_saved_checkbox_visibility(operator, condition, value):
    rule = {"field": "flag", operator: [condition] if operator == "in" else condition}
    pack = validate_form_pack_schema(pack_for(field("flag", "checkbox"), field("answer", "text", visible_when=rule)))
    assert submit(pack, flag=value, answer="kept")["submitted_values"]["answer"] == "kept"
    assert "answer" not in submit(pack, flag=not value, answer="hidden")["submitted_values"]


@pytest.mark.parametrize("condition", [False, 0, None])
@pytest.mark.parametrize("operator", ["equals", "in"])
def test_schema_preserves_typed_visibility(condition, operator):
    rule = {"field": "amount", operator: [condition] if operator == "in" else condition}
    pack = validate_form_pack_schema(pack_for(field(), field("answer", "text", visible_when=rule)))
    assert pack["forms"][0]["fields"][1]["visible_when"] == rule


@pytest.mark.parametrize("operator", ["equals", "in"])
@pytest.mark.parametrize("kind, current, expected, visible", [
    ("number", 0, 0, True), ("number", None, None, True), ("number", 1, 0, False),
    ("select", "TRUE", "TRUE", True), ("select", "true", "TRUE", False),
    ("multi_select", ["TRUE", "other"], "TRUE", True),
])
def test_saved_visibility_preserves_zero_null_and_case(kind, current, expected, visible, operator):
    rule = {"field": "kind", operator: [expected] if operator == "in" else expected}
    dependency = field("kind", kind, options=[{"value": item, "label": item} for item in ["TRUE", "true", "other"]])
    pack = validate_form_pack_schema(pack_for(dependency, field("answer", "text", visible_when=rule)))
    assert ("answer" in submit(pack, kind=current, answer="kept")["submitted_values"]) is visible


def test_hidden_invalid_value_does_not_block_submission():
    pack = pack_for(field("kind", "text"), field(visible_when={"field": "kind", "equals": "quantity"}))
    result = submit(pack, kind="other", amount="invalid")
    assert "amount" not in result["submitted_values"]
    assert all(row["key"] != "amount" for row in result["summary_rows"])


def test_hidden_priority_field_is_not_reintroduced_by_legacy_fallback():
    pack = pack_for(field("kind", "text"), field(visible_when={"field": "kind", "equals": "quantity"}))
    pack["forms"][0]["priority_policy"] = {"impact_field": "amount"}
    assert "amount" not in submit(pack, kind="other", amount="invalid")["submitted_values"]


def test_visible_invalid_value_is_rejected():
    with pytest.raises(ValueError, match="Недопустимое значение"):
        submit(pack_for(field()), amount="invalid")


def test_invalid_visibility_dependency_is_rejected():
    pack = pack_for(field(), field("answer", "text", visible_when={"field": "amount", "equals": 1}))
    with pytest.raises(ValueError, match="amount"):
        submit(pack, amount="invalid", answer="hidden")


@pytest.mark.parametrize("alias", ["pattern", "regex"])
def test_schema_rejects_invalid_pattern(alias):
    with pytest.raises(ValueError, match="pattern|regex"):
        validate_form_pack_schema(pack_for(field("code", "text", validation={alias: "["})))


@pytest.mark.parametrize("alias", ["pattern", "regex"])
@pytest.mark.parametrize("pattern", ["(a)?(?(1)b|c)", "(?#comment)a"])
def test_python_only_groups_cannot_be_published_or_used_by_saved_forms(alias, pattern):
    pack = pack_for(field("code", "text", validation={alias: pattern}))
    with pytest.raises(ValueError, match="shared Python/JavaScript syntax"):
        validate_form_pack_schema(pack)
    with pytest.raises(ValueError, match="Ошибка настройки формата поля"):
        submit(pack, code="c")


def test_submission_does_not_ignore_invalid_saved_pattern():
    with pytest.raises(ValueError):
        submit(pack_for(field("code", "text", validation={"pattern": "["})), code="anything")


@pytest.mark.parametrize("pattern, value", [(r"^\++$", "+++"), (r"^\?+$", "???"), ("[++]", "+"),
    (r"^\(\?\(1\)\)$", "(?(1))"), (r"^\(\?#comment\)a$", "(?#comment)a"), ("[?(#]+", "?(#")])
def test_shared_pattern_accepts_escaped_quantifiers_and_character_classes(pattern, value):
    pack = validate_form_pack_schema(pack_for(field("code", "text", validation={"pattern": pattern})))
    assert submit(pack, code=value)["submitted_values"]["code"] == value


@pytest.mark.parametrize("alias", ["pattern", "regex"])
def test_valid_unicode_pattern_and_metadata_survive_normalization(alias):
    pack = validate_form_pack_schema(pack_for(field("code", "text", validation={alias: "^[А-Яа-я]+$"})))
    assert submit(deepcopy(pack), code="Ёж".replace("Ё", "Е"))["submitted_values"]["code"] == "Еж"
    with pytest.raises(ValueError):
        submit(pack, code="123")


@pytest.mark.parametrize("value", [
    "person@example.test", "имя@пример.рф", "x@...", "x@a..", "x@..a",
    '"x"@example.test', "x@a\ufeff.b", "  person@example.test\n",
])
def test_email_preserves_existing_permissive_policy(value):
    result = submit(pack_for(field("email", "email")), email=value)
    assert result["submitted_values"]["email"] == value.strip()


@pytest.mark.parametrize("value", [
    "@example.test", "person@", "person.example.test", "person@@example.test",
    "x@.a", "x@a.", "x@..", "x@a b.test", "x y@a.test", "x@a\n.b",
    "x@a\u00a0.b", "x@a\u001c.b", "x@a\u0085.b",
])
def test_email_rejects_missing_parts_extra_at_and_python_whitespace(value):
    with pytest.raises(ValueError, match="Укажите корректный email"):
        submit(pack_for(field("email", "email")), email=value)


def test_email_accepts_long_valid_domain_without_an_implicit_length_limit():
    value = "x@" + "." * 100_000
    assert submit(pack_for(field("email", "email")), email=value)["submitted_values"]["email"] == value


def test_email_rejects_long_dotted_domain_without_blocking_validation():
    # A subprocess bounds the regression: the old ambiguous regex exceeds this
    # timeout; linear validation (including startup) has ample time.
    script = """
import sys
sys.path.insert(0, "server")
from tickets.form_field_values import validate_form_submission
pack = {"forms": [{"key": "probe", "fields": [{"key": "email", "type": "email"}]}]}
try:
    validate_form_submission(pack, form_key="probe", raw_values={"email": "x@" + "." * 100_000 + "@"})
except ValueError as exc:
    assert "Укажите корректный email" in str(exc)
else:
    raise AssertionError("Malformed email was accepted")
"""
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=5,
        check=True,
    )

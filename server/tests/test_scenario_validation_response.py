"""Draft validation responses without database access or submitted values."""
import json
from contextlib import asynccontextmanager

import pytest

from web_api import request_scenario_admin_handlers as handlers
from web_api.dto.request_scenario_admin import ScenarioSave
from pydantic import BaseModel, ValidationError, model_validator


@pytest.mark.asyncio
async def test_draft_validation_identifies_field_without_echoing_input(monkeypatch):
    @asynccontextmanager
    async def session():
        yield object()

    monkeypatch.setattr(handlers, "get_session", session)

    async def invalid(_repo):
        ScenarioSave.model_validate({"revision": 1, "definition": {
            "scenario_key": "test", "service_code": "it", "offering_full_code": "it.test",
            "title": "x" * 301, "process_binding": {"request_template_key": "test"},
        }})

    response = await handlers._run({"auth_context": object()}, invalid)
    payload = json.loads(response.body)
    assert response.status == 400
    assert payload["error_code"] == "VALIDATION_ERROR"
    assert payload["issues"] == [{"code": "string_too_long", "path": "definition.title",
                                  "message": "Сократите текст: не более 300 символов."}]
    assert "x" * 301 not in response.text
    assert "input" not in response.text and "ctx" not in response.text


@pytest.mark.parametrize(("error", "expected"), [
    ("choice field requires options", "Добавьте варианты ответа для вопроса с выбором."),
    ("option values must be unique", "Значения вариантов ответа должны различаться."),
    ("private validator text", "Проверьте тип, формат и допустимый диапазон значения."),
])
def test_validator_reasons_use_only_known_safe_messages(error, expected):
    class Invalid(BaseModel):
        @model_validator(mode="after")
        def invalid(self):
            raise ValueError(error)

    with pytest.raises(ValidationError) as failure:
        Invalid.model_validate({})
    issue = handlers._validation_issues(failure.value)[0]
    assert issue["message"] == expected
    assert error not in json.dumps(issue)

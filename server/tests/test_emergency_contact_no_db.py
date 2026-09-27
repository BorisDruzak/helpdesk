from types import SimpleNamespace

import pytest

from web_api.requester_handlers import _has_contact_for_emergency

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize("person", [None, SimpleNamespace(phone=None, email=None)])
def test_display_name_alone_is_not_an_emergency_contact(person):
    assert not _has_contact_for_emergency(person, {}, {"user_display_name": "Test Requester"})


@pytest.mark.parametrize("field,value", [("phone", "+7 000 123-45-67"), ("email", "requester@example.test")])
def test_person_phone_or_email_remains_an_emergency_contact(field, value):
    person = SimpleNamespace(phone=None, email=None)
    setattr(person, field, value)
    assert _has_contact_for_emergency(person, {}, {})


@pytest.mark.parametrize("source", ["form", "request"])
def test_explicit_callback_contact_remains_accepted(source):
    contact = {"callback_phone": "+7 000 123-45-67"}
    assert _has_contact_for_emergency(None, contact if source == "form" else {},
                                      contact if source == "request" else {})


def test_blank_contacts_do_not_satisfy_emergency_contact_requirement():
    assert not _has_contact_for_emergency(SimpleNamespace(phone=" ", email=None),
                                          {"contact_phone": " "}, {"email": ""})

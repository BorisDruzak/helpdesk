import pytest

from auth.requester_registration import registration_login_base

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize("first,last,expected", [
    ("Иван", "Петров", "ipetrov"),
    ("Юрий", "Ёлкин", "yuyolkin"),
    ("  Анна ", "Салтыкова-Щедрина", "asaltykova-shchedrina"),
    ("Илья", "Соловьёв", "isolovyov"),
    ("John", "Smith", "jsmith"),
])
def test_registration_transliterates_initial_and_surname(first, last, expected):
    assert registration_login_base(first, last) == expected


@pytest.mark.parametrize("first,last", [("", "Петров"), ("Иван", ""), ("1", "Петров"), ("Иван", "🙂"), ("Иван", "--")])
def test_registration_rejects_unsupported_or_empty_names(first, last):
    with pytest.raises(ValueError):
        registration_login_base(first, last)

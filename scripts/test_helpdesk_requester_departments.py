import pytest

from scripts.helpdesk_requester_departments import load_department_names, require_database


def test_names_only_catalog_is_unique_for_both_employee_groups():
    names = load_department_names()
    assert len(names) == len(set(name.casefold() for name in names)) == 30
    assert names.count("Управление муниципальной службы") == 1
    assert names.count("Отдел по делам гражданской обороны, антитеррористическим и чрезвычайным ситуациям") == 1
    assert "Бухгалтерский отдел" in names
    assert not any("Synthetic" in name or "муниципальных служащих" in name for name in names)


@pytest.mark.parametrize("database", ["helpdesk", "helpdesk_db", "postgres", "pc_support_test_template"])
def test_catalog_refuses_nonstaging_database(database):
    with pytest.raises(ValueError):
        require_database(database)


def test_test_database_must_be_explicit_and_isolated():
    require_database("helpdesk_staging_db")
    require_database("pc_support_test_run123", isolated_test=True)
    with pytest.raises(ValueError):
        require_database("helpdesk_staging_db", isolated_test=True)

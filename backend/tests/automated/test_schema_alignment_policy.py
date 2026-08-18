"""Schema drift policy for explicitly non-ORM infrastructure tables."""

from app.database_schema import NON_ORM_SCHEMA_TABLES, include_object


def test_only_seed_marks_is_excluded_from_alembic_orm_comparison():
    assert NON_ORM_SCHEMA_TABLES == frozenset({"demo_seed_marks"})
    assert include_object(object(), "demo_seed_marks", "table", True, None) is False
    assert include_object(object(), "users", "table", True, None) is True
    assert include_object(object(), "demo_seed_marks", "column", True, None) is True
    assert include_object(object(), "demo_seed_marks", "table", False, None) is True

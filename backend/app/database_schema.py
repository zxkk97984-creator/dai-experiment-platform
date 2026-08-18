"""Explicit policy for database objects outside the SQLAlchemy ORM.

The demo seed ownership table is intentionally created and managed by the seed
runtime rather than Alembic or the business ORM.  Keep this allow-list narrow:
an unexpected extra table must still be reported as schema drift.
"""

NON_ORM_SCHEMA_TABLES = frozenset({"demo_seed_marks"})


def include_object(object_, name: str, type_: str, reflected: bool, compare_to) -> bool:
    """Return whether Alembic should include an object in ORM comparison."""
    del object_, compare_to
    return not (
        type_ == "table"
        and reflected
        and name in NON_ORM_SCHEMA_TABLES
    )

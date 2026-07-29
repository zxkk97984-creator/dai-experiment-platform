import importlib.util
from pathlib import Path

import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "a7b8c9d0e112_ai_code_grading_v1.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("ai_code_grading_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeDialect:
    name = "mysql"


class _FakeBind:
    dialect = _FakeDialect()


class _FakeOp:
    def __init__(self):
        self.added_columns = []
        self.created_tables = []
        self.created_indexes = []

    def get_bind(self):
        return _FakeBind()

    def add_column(self, table_name, column):
        self.added_columns.append((table_name, column.name))

    def create_table(self, table_name, *args, **kwargs):
        self.created_tables.append(table_name)

    def create_index(self, index_name, table_name, columns):
        self.created_indexes.append((index_name, table_name, columns))


class _FakeInspector:
    def get_columns(self, table_name):
        assert table_name == "judge_questions"
        return [{"name": "grading_mode"}]

    def get_table_names(self):
        return ["question_rubrics"]

    def get_indexes(self, table_name):
        assert table_name == "judge_questions"
        return [{"name": "ix_judge_questions_grading_mode"}]


def test_mysql_json_default_uses_expression_syntax(monkeypatch):
    migration = _load_migration()
    monkeypatch.setattr(migration, "op", _FakeOp())

    default = migration._json_server_default("{}")

    assert str(default) == "('{}')"


def test_add_missing_columns_skips_columns_left_by_partial_mysql_migration(monkeypatch):
    migration = _load_migration()
    fake_op = _FakeOp()
    monkeypatch.setattr(migration, "op", fake_op)
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: _FakeInspector())

    migration._add_missing_columns(
        "judge_questions",
        [
            sa.Column("grading_mode", sa.String(length=20)),
            sa.Column("teacher_constraints", sa.JSON()),
        ],
    )

    assert fake_op.added_columns == [("judge_questions", "teacher_constraints")]


def test_create_table_skips_table_left_by_later_partial_mysql_migration(monkeypatch):
    migration = _load_migration()
    fake_op = _FakeOp()
    monkeypatch.setattr(migration, "op", fake_op)
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: _FakeInspector())

    migration._create_table_if_missing(
        "question_rubrics",
        sa.Column("id", sa.Integer(), primary_key=True),
    )

    assert fake_op.created_tables == []


def test_create_index_skips_index_left_by_later_partial_mysql_migration(monkeypatch):
    migration = _load_migration()
    fake_op = _FakeOp()
    monkeypatch.setattr(migration, "op", fake_op)
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: _FakeInspector())

    migration._create_index_if_missing(
        "ix_judge_questions_grading_mode",
        "judge_questions",
        ["grading_mode"],
    )

    assert fake_op.created_indexes == []

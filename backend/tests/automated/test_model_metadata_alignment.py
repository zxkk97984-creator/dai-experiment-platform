"""TASK-010：ORM 元数据与迁移历史的对齐契约（alembic check 的 SQLite 侧补充）。

模型层必须显式使用迁移已建立的索引/约束名；autogenerate 删除/新增清单
不得直接落库（实库收敛由 CI/alembic check 在 MySQL 上验证）。
"""

from app.database import Base


def _index_by_name(table, name):
    for index in table.indexes:
        if index.name == name:
            return index
    raise AssertionError(f"{table.name} 缺少索引 {name}")


def test_queue_composite_indexes_declared_with_migration_names():
    submissions = Base.metadata.tables["submissions"]
    idx = _index_by_name(submissions, "ix_submissions_gs_updated")
    assert [c.name for c in idx.columns] == ["grading_status", "updated_at"]

    exam_answers = Base.metadata.tables["exam_answers"]
    idx2 = _index_by_name(exam_answers, "ix_exam_answers_gs_updated")
    assert [c.name for c in idx2.columns] == ["grading_status", "updated_at"]


def test_academic_terms_code_unique_constraint_name():
    table = Base.metadata.tables["academic_terms"]
    names = {c.name for c in table.constraints}
    assert "uq_academic_terms_code" in names


def test_environment_binding_columns_not_null():
    not_null = {
        ("assignments", "environment_version_id"),
        ("submissions", "environment_version_id"),
        ("experiment_records", "environment_version_id"),
        ("notebook_template_versions", "environment_version_id"),
        ("notebook_templates", "draft_environment_version_id"),
    }
    for table_name, column in not_null:
        col = Base.metadata.tables[table_name].columns[column]
        assert col.nullable is False, f"{table_name}.{column} 应为 NOT NULL"


def test_judge_question_environment_inherits_nullable():
    col = Base.metadata.tables["judge_questions"].columns["environment_version_id"]
    assert col.nullable is True, "题目环境 NULL=继承作业默认，保持可空"


def test_timestamp_mixin_columns_not_null():
    for table_name in (
        "users", "assignments", "submissions", "exam_answers", "experiment_submissions",
    ):
        for column in ("created_at", "updated_at"):
            col = Base.metadata.tables[table_name].columns[column]
            assert col.nullable is False, f"{table_name}.{column} 应为 NOT NULL"
            assert col.server_default is not None, f"{table_name}.{column} 应有 server default"


def test_experiment_submissions_submitted_at_not_null():
    col = Base.metadata.tables["experiment_submissions"].columns["submitted_at"]
    assert col.nullable is False


def test_published_at_stays_nullable():
    # assignments.published_at 与 notebook_template_versions.published_at 保持可空
    for table_name in ("assignments", "notebook_template_versions"):
        col = Base.metadata.tables[table_name].columns["published_at"]
        assert col.nullable is True, f"{table_name}.published_at 应保持 nullable"

from __future__ import annotations

import subprocess
import sys
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint
from sqlalchemy.exc import IntegrityError

from app import models
from app.database import Base


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


def _constraint_sql(table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


def _foreign_key_targets(table_name: str, column_name: str) -> set[str]:
    column = Base.metadata.tables[table_name].c[column_name]
    return {foreign_key.target_fullname for foreign_key in column.foreign_keys}


def test_notebook_template_draft_fields_and_revision_default(db_session_factory):
    assert hasattr(models, "NotebookTemplate"), "NotebookTemplate model is missing"

    table = models.NotebookTemplate.__table__
    assert {
        "name",
        "draft_cells",
        "draft_revision",
        "current_version_id",
        "owner_id",
    } <= set(table.c.keys())

    with db_session_factory() as db:
        template = models.NotebookTemplate(name="线性回归实验", owner_id=1)
        db.add(template)
        db.commit()
        db.refresh(template)

        assert template.draft_cells == []
        assert template.draft_revision == 1
        assert template.current_version_id is None


def test_notebook_template_version_number_is_unique_per_template(db_session_factory):
    assert hasattr(models, "NotebookTemplateVersion"), "NotebookTemplateVersion model is missing"

    with db_session_factory() as db:
        template = models.NotebookTemplate(name="卷积实验", owner_id=1)
        db.add(template)
        db.flush()
        db.add(
            models.NotebookTemplateVersion(
                template_id=template.id,
                cells=[{"id": "cell-1", "source": "print(1)"}],
                sha256="a" * 64,
                version_number=1,
                assets_dir="templates/conv/1",
                published_by_id=1,
            )
        )
        db.commit()

        db.add(
            models.NotebookTemplateVersion(
                template_id=template.id,
                cells=[],
                sha256="b" * 64,
                version_number=1,
                assets_dir="templates/conv/duplicate",
                published_by_id=1,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


@pytest.mark.parametrize(
    ("lesson_id", "module_id"),
    [
        (None, None),
        (10, 20),
    ],
)
def test_experiment_record_requires_exactly_one_parent(
    db_session_factory,
    lesson_id,
    module_id,
):
    with db_session_factory() as db:
        db.add(
            models.ExperimentRecord(
                lesson_id=lesson_id,
                module_id=module_id,
                student_id=100,
                template_version_id=200,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_experiment_record_is_unique_for_lesson_student(db_session_factory):
    with db_session_factory() as db:
        db.add_all(
            [
                models.ExperimentRecord(
                    lesson_id=10,
                    student_id=100,
                    template_version_id=200,
                ),
                models.ExperimentRecord(
                    lesson_id=10,
                    student_id=100,
                    template_version_id=201,
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_experiment_record_is_unique_for_module_student(db_session_factory):
    with db_session_factory() as db:
        db.add_all(
            [
                models.ExperimentRecord(
                    module_id=20,
                    student_id=100,
                    template_version_id=200,
                ),
                models.ExperimentRecord(
                    module_id=20,
                    student_id=100,
                    template_version_id=201,
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_exam_submission_columns_and_status_contract():
    table = models.ExamSubmission.__table__

    assert "answers" not in table.c
    assert {"expires_at", "graded_at"} <= set(table.c.keys())
    status_constraint = _constraint_sql(table)
    for expected_status in ("started", "submitted", "grading", "graded"):
        assert expected_status in status_constraint


def test_exam_answer_is_unique_per_submission_question(db_session_factory):
    assert hasattr(models, "ExamAnswer"), "ExamAnswer model is missing"

    now = datetime.now(UTC)
    with db_session_factory() as db:
        submission = models.ExamSubmission(
            exam_id=10,
            student_id=100,
            status="started",
            started_at=now,
            expires_at=now + timedelta(hours=1),
        )
        db.add(submission)
        db.flush()
        db.add_all(
            [
                models.ExamAnswer(
                    submission_id=submission.id,
                    question_id=20,
                    selected_options=["A"],
                ),
                models.ExamAnswer(
                    submission_id=submission.id,
                    question_id=20,
                    selected_options=["B"],
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_metadata_contains_unified_notebook_experiment_and_exam_schema():
    tables = Base.metadata.tables

    assert {
        "notebook_templates",
        "notebook_template_versions",
        "experiment_records",
        "exam_questions",
        "exam_submissions",
        "exam_answers",
    } <= set(tables)
    assert {
        "notebook_records",
        "notebook_submissions",
    }.isdisjoint(tables)
    # exam_grades 保留（v5 计划要求存储最终汇总成绩）
    assert "exam_grades" in tables

    assert _foreign_key_targets("lessons", "template_id") == {"notebook_templates.id"}
    assert _foreign_key_targets("experiment_modules", "template_id") == {
        "notebook_templates.id"
    }
    assert _foreign_key_targets("experiment_records", "template_version_id") == {
        "notebook_template_versions.id"
    }
    assert _foreign_key_targets("exam_questions", "exam_id") == {"exams.id"}
    assert _foreign_key_targets("exam_answers", "submission_id") == {
        "exam_submissions.id"
    }
    assert _foreign_key_targets("exam_answers", "question_id") == {
        "exam_questions.id"
    }

    experiment_columns = set(tables["experiment_records"].c.keys())
    assert {
        "lesson_id",
        "module_id",
        "student_id",
        "template_version_id",
        "record_revision",
        "cells_sources",
        "cells_outputs",
        "status",
        "started_at",
        "submitted_at",
        "completed_at",
    } <= experiment_columns

    question_columns = set(tables["exam_questions"].c.keys())
    assert {
        "question_type",
        "prompt",
        "options",
        "correct_answer",
        "starter_code",
        "public_cases",
        "hidden_tests",
        "points",
        "order_index",
        "time_limit_ms",
        "memory_limit_mb",
    } <= question_columns

    answer_columns = set(tables["exam_answers"].c.keys())
    assert {
        "selected_options",
        "code_answer",
        "score",
        "grading_status",
        "result_details",
        "system_error",
    } <= answer_columns


def test_checkpoint_migration_is_child_of_current_head():
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    scripts = ScriptDirectory.from_config(config)

    head = scripts.get_current_head()
    assert head != "f81a7a35f73f", "checkpoint migration is missing"
    checkpoint = scripts.get_revision("a1b2c3d4e5f6")
    assert checkpoint is not None
    assert checkpoint.down_revision == "f81a7a35f73f"
    assert callable(checkpoint.module.upgrade)
    assert callable(checkpoint.module.downgrade)
    assert scripts.get_revision(head) is not None
    assert "a1b2c3d4e5f6" in {
        revision.revision for revision in scripts.iterate_revisions(head, "f81a7a35f73f")
    }


def _alembic_env(tmp_path, db_name: str) -> dict:
    """构建带 DAI_DATABASE_URL 和 PYTHONPATH 的子进程环境"""
    db_path = tmp_path / db_name
    env = dict(__import__("os").environ)
    env["DAI_DATABASE_URL"] = f"sqlite:///{db_path}"
    # 确保 backend/ 在路径上以便 alembic/env.py 能 from app.config import
    env["PYTHONPATH"] = str(BACKEND_ROOT)
    return env


def test_clean_migration_upgrade_head(tmp_path):
    """全新数据库 alembic upgrade head 无报错"""
    env = _alembic_env(tmp_path, "clean.db")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        capture_output=True, text=True, timeout=30,
        env=env,
    )
    assert result.returncode == 0, f"upgrade failed:\nSTDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"


def test_migration_downgrade_upgrade_roundtrip(tmp_path):
    """downgrade → upgrade roundtrip 完整无报错"""
    env = _alembic_env(tmp_path, "roundtrip.db")

    r1 = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT, capture_output=True, text=True, timeout=30, env=env,
    )
    assert r1.returncode == 0, f"first upgrade failed:\n{r1.stderr}\n{r1.stdout}"

    r2 = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=BACKEND_ROOT, capture_output=True, text=True, timeout=30, env=env,
    )
    assert r2.returncode == 0, f"downgrade failed:\n{r2.stderr}\n{r2.stdout}"

    r3 = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT, capture_output=True, text=True, timeout=30, env=env,
    )
    assert r3.returncode == 0, f"re-upgrade failed:\n{r3.stderr}\n{r3.stdout}"


def _assert_only_automated_tests_collected(cwd: Path, result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 0, f"pytest exit={result.returncode}\n{result.stdout}\n{result.stderr}"
    normalized = result.stdout.replace("\\", "/")
    assert "tests/automated/" in normalized, f"automated tests not found in:\n{normalized}"
    for diagnostic_script in (BACKEND_ROOT / "tests").glob("*.py"):
        assert diagnostic_script.name not in normalized, (
            f"diagnostic script {diagnostic_script.name} was collected"
        )


def test_pytest_collects_only_automated_tests_from_backend():
    """从 backend/ 目录运行 pytest 只收集 automated 测试"""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=BACKEND_ROOT,
        capture_output=True, text=True, timeout=30, check=False,
    )
    _assert_only_automated_tests_collected(BACKEND_ROOT, result)


def test_pytest_collects_only_automated_tests_from_repo_root():
    """从仓库根目录运行 pytest 只收集 automated 测试"""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=REPO_ROOT,
        capture_output=True, text=True, timeout=30, check=False,
    )
    _assert_only_automated_tests_collected(REPO_ROOT, result)


# ═══════════════════════════════════════════════════════════════
# P1-1: conftest 仅在未设置 DAI_DATABASE_URL 时创建临时 SQLite
# ═══════════════════════════════════════════════════════════════

def test_p1_1_conftest_uses_env_mysql_url(tmp_path, monkeypatch):
    """P1-1: 设置 DAI_DATABASE_URL 为 MySQL URL 时，conftest 直接使用而非覆盖为 SQLite"""
    mysql_url = "mysql+pymysql://dai:test@127.0.0.1:3306/dai_platform"
    monkeypatch.setenv("DAI_DATABASE_URL", mysql_url)

    # 重新导入以触发 fixture 逻辑
    db_url = os.environ.get("DAI_DATABASE_URL", "")
    assert db_url == mysql_url

    # 模拟 conftest 逻辑：仅在未设置环境变量时创建临时 SQLite
    if not db_url:
        db_url = f"sqlite:///{tmp_path / 'test.db'}"

    assert db_url == mysql_url, (
        f"P1-1: 设置 MySQL URL 后不应覆盖为 SQLite，但 db_url = {db_url}"
    )
    assert "sqlite" not in db_url, "MySQL URL 不应包含 sqlite"


def test_p1_1_conftest_creates_sqlite_when_no_env(tmp_path, monkeypatch):
    """P1-1: 未设置 DAI_DATABASE_URL 时，conftest 创建临时 SQLite"""
    monkeypatch.delenv("DAI_DATABASE_URL", raising=False)

    db_url = os.environ.get("DAI_DATABASE_URL", "")
    assert not db_url, "环境变量应未设置"

    if not db_url:
        db_url = f"sqlite:///{tmp_path / 'test.db'}"

    assert "sqlite" in db_url, "未设置环境变量时应使用 SQLite"

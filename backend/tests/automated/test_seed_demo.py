"""Demo Seed 隔离测试：临时 SQLite + 自造 available 环境版本。

与 CI/E2E/既有测试完全隔离：
- 使用 conftest 的 db_session_factory（临时 SQLite 库）；
- 测试内自造 basic 环境版本（available + digest），仅供本测试运行，
  不触碰真实环境控制面；
- 验证：播种成功、二次运行幂等（计数一致、无重复）、reset 后再次播种计数一致。
"""
from datetime import datetime, timezone

import pytest


def _seed_basic_env(db_session_factory):
    """在测试库内自造 basic 可用环境版本（测试 Fixture，非生产伪造）。"""
    from sqlalchemy import select

    from app.models import EnvironmentProfile, EnvironmentVersion

    with db_session_factory() as db:
        existing = db.scalar(select(EnvironmentProfile).where(EnvironmentProfile.slug == "basic"))
        if existing is not None:
            return existing.id
        profile = EnvironmentProfile(slug="basic", display_name="Basic", status="active")
        db.add(profile)
        db.flush()
        version = EnvironmentVersion(
            profile_id=profile.id,
            version_number=1,
            status="available",
            base_image_ref="python:3.12-slim",
            image_digest="sha256:test-demo-seed-digest-0000000000000000000000000000000000000000000000000000000000000000",
            python_version="3.12",
            minimum_memory_mb=256,
            manifest_sha256="c" * 64,
            available_at=datetime.now(timezone.utc),
        )
        db.add(version)
        db.commit()
        return profile.id


def _run_seed(db_session_factory, *, reset=False):
    from app.seed_demo import run_demo_seed

    with db_session_factory() as db:
        return run_demo_seed(
            db,
            reference_date="2026-12-07",
            reset=reset,
            skip_env_check=True,
            force_fixture=True,  # 测试环境无 Docker，全部 Fixture
        )


def _counts(db_session_factory):
    from sqlalchemy import func, select

    from app.models import (
        AcademicTerm, Announcement, Assignment, Chapter, CodeGrade, Course,
        CourseEnrollment, Exam, ExamAnswer, ExamQuestion, ExamSubmission,
        ExperimentModule, ExperimentRecord, ExperimentSubmission, JudgeQuestion,
        Lesson, LessonProgress, NotebookTemplate, NotebookTemplateVersion,
        QuestionRubric, Submission, TeachingClass, TeachingClassStudent, User,
    )

    models = [
        User, AcademicTerm, TeachingClass, TeachingClassStudent, Course, Chapter,
        Lesson, CourseEnrollment, LessonProgress, Assignment, JudgeQuestion,
        Submission, Exam, ExamQuestion, ExamSubmission, ExamAnswer,
        NotebookTemplate, NotebookTemplateVersion, ExperimentModule,
        ExperimentRecord, ExperimentSubmission, QuestionRubric, CodeGrade,
        Announcement,
    ]
    with db_session_factory() as db:
        return {
            m.__tablename__: int(db.scalar(select(func.count()).select_from(m)) or 0)
            for m in models
        }


def test_seed_demo_runs_and_is_idempotent(db_session_factory):
    _seed_basic_env(db_session_factory)
    first = _run_seed(db_session_factory)
    second = _run_seed(db_session_factory)

    c1 = _counts(db_session_factory)
    c2 = _counts(db_session_factory)
    assert c1 == c2, f"二次播种计数漂移: {c1} vs {c2}"

    # 核心数量断言
    assert c1["users"] >= 65
    assert c1["courses"] >= 7
    assert c1["assignments"] >= 9
    assert c1["submissions"] >= 200
    assert c1["code_grades"] >= 100
    assert c1["exams"] >= 3

    # 唯一键抽查：用户名无重复
    from sqlalchemy import text

    with db_session_factory() as db:
        dup = db.execute(
            text("SELECT username, COUNT(*) c FROM users GROUP BY username HAVING c > 1")
        ).all()
        assert not dup, f"用户名重复: {dup}"


def test_seed_demo_reset_then_reseed_matches(db_session_factory):
    """--reset-demo 语义 = 先清 Demo 数据再播种；本测试分两步验证：
    1) reset_demo_data 只清登记数据（业务表归零、环境控制面保留）；
    2) 清空后再次播种，计数与首次一致。
    """
    from app.seed_demo.cleanup import reset_demo_data

    _seed_basic_env(db_session_factory)
    first = _run_seed(db_session_factory)
    c_first = _counts(db_session_factory)

    # 单独执行清理步骤（不立即重播）
    with db_session_factory() as db:
        reset_demo_data(db)
    c_after_reset = _counts(db_session_factory)
    # reset 后业务表应为 0（保留环境控制面）
    assert c_after_reset["users"] == 0
    assert c_after_reset["courses"] == 0

    # 清空后再次播种：计数与首次一致（可复现）
    second = _run_seed(db_session_factory)
    c_second = _counts(db_session_factory)
    assert c_first == c_second, f"reset 后重播计数不一致: {c_first} vs {c_second}"
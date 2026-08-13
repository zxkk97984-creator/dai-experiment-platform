"""环境版本业务绑定测试（Phase 3）

覆盖（plan 4.6「业务绑定字段」）：
- seed basic available 后，ORM 创建业务记录自动绑定 basic 当前可用版本（惰性默认）
- 显式指定环境版本可覆盖默认
- 策略字段默认值：作业/提交/Notebook unrestricted，题目 inherit，白名单为空
- Submission 环境与策略快照字段
- ExperimentRecord 创建时绑定环境
- 无 basic 可用版本时模型层拒绝 NULL（TASK-010：NOT NULL + 惰性默认绑定）

说明：开发库（MySQL）尚未跑迁移 A/B，本测试全部使用隔离 SQLite 测试库。
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Assignment,
    Course,
    EnvironmentProfile,
    EnvironmentVersion,
    ExperimentRecord,
    JudgeQuestion,
    NotebookTemplate,
    NotebookTemplateVersion,
    Submission,
    User,
)
from app.services.environment_seed import seed_environment_catalog


def _seed_basic_available(db, settings) -> int:
    """幂等 seed 后把 basic v1 标记为 available（带 digest），返回版本 id。"""
    seed_environment_catalog(db, settings)
    version = db.scalar(
        select(EnvironmentVersion)
        .join(EnvironmentProfile, EnvironmentProfile.id == EnvironmentVersion.profile_id)
        .where(
            EnvironmentProfile.slug == "basic",
            EnvironmentVersion.version_number == 1,
        )
    )
    assert version is not None, "seed 后 basic v1 应存在"
    if version.status != "available":
        version.status = "available"
        version.image_digest = "sha256:" + "a" * 64
        version.python_version = "3.12"
        db.commit()
    return version.id


def _make_user(db, username="stu"):
    user = User(
        username=username,
        real_name=username,
        role="student",
        status="active",
        password_hash="x",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ═══════════════════════════════════════════════════════════════
# 作业 / 题目 / 提交
# ═══════════════════════════════════════════════════════════════

def test_assignment_binds_basic_by_default(db_session_factory, test_settings):
    """创建作业未指定环境时，惰性绑定 basic 当前可用版本（plan 4.6 assignments）"""
    with db_session_factory() as db:
        basic_id = _seed_basic_available(db, test_settings)
        course = Course(title="C1", status="published")
        db.add(course)
        db.commit()
        db.refresh(course)
        assignment = Assignment(course_id=course.id, title="A1", status="draft")
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        assert assignment.environment_version_id == basic_id
        assert assignment.import_policy_mode == "unrestricted"
        assert assignment.allowed_imports == []


def test_assignment_explicit_environment_overrides_default(db_session_factory, test_settings):
    with db_session_factory() as db:
        basic_id = _seed_basic_available(db, test_settings)
        # seed 已创建 data 档位（v1 为 draft），手动补一个 data v2 available 版本
        data_profile = db.scalar(
            select(EnvironmentProfile).where(EnvironmentProfile.slug == "data")
        )
        assert data_profile is not None, "seed 后 data 档位应存在"
        data_version = EnvironmentVersion(
            profile_id=data_profile.id,
            version_number=2,
            status="available",
            base_image_ref="python:3.12-slim",
            # conftest 预置的 basic 版本占用 "b"*64 摘要；image_digest 有
            # UNIQUE 约束，换用独立摘要避免冲突
            image_digest="sha256:" + "c" * 64,
            minimum_memory_mb=768,
            manifest_sha256="m" * 64,
        )
        db.add(data_version)
        db.commit()
        db.refresh(data_version)

        course = Course(title="C1", status="published")
        db.add(course)
        db.commit()
        db.refresh(course)
        assignment = Assignment(
            course_id=course.id, title="A2", status="draft",
            environment_version_id=data_version.id,
        )
        db.add(assignment)
        db.commit()
        assert assignment.environment_version_id == data_version.id
        assert assignment.environment_version_id != basic_id


def test_judge_question_defaults_to_inherit(db_session_factory, test_settings):
    """题目默认 import 策略为 inherit（继承作业）；环境字段 NULL = 继承作业默认（plan 4.6 judge_questions）

    Phase 4 起题目环境由服务层/API 层显式传参；存量回填由迁移 B 绑定 basic，新题目不自动绑定。
    """
    with db_session_factory() as db:
        basic_id = _seed_basic_available(db, test_settings)
        course = Course(title="C1", status="published")
        db.add(course)
        db.commit()
        db.refresh(course)
        assignment = Assignment(course_id=course.id, title="A1", status="draft")
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        question = JudgeQuestion(
            assignment_id=assignment.id, title="Q1",
            function_name="add", hidden_tests="assert True",
        )
        db.add(question)
        db.commit()
        assert question.environment_version_id is None  # NULL 语义：继承作业默认环境
        assert question.import_policy_mode == "inherit"
        assert question.allowed_imports == []


def test_submission_snapshots_environment_and_policy(db_session_factory, test_settings):
    """提交保存环境版本与 import 策略快照（plan 4.6 submissions）"""
    with db_session_factory() as db:
        basic_id = _seed_basic_available(db, test_settings)
        student = _make_user(db)
        course = Course(title="C1", status="published")
        db.add(course)
        db.commit()
        db.refresh(course)
        assignment = Assignment(course_id=course.id, title="A1", status="published")
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        question = JudgeQuestion(
            assignment_id=assignment.id, title="Q1",
            function_name="add", hidden_tests="assert True",
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        submission = Submission(question_id=question.id, student_id=student.id, code="print(1)")
        db.add(submission)
        db.commit()
        assert submission.environment_version_id == basic_id
        assert submission.import_policy_mode_snapshot == "unrestricted"
        assert submission.allowed_imports_snapshot == []


# ═══════════════════════════════════════════════════════════════
# Notebook 模板 / 版本 / 实验记录
# ═══════════════════════════════════════════════════════════════

def test_notebook_template_draft_binds_environment(db_session_factory, test_settings):
    """Notebook 草稿保存 draft_* 环境字段（plan 4.6 notebook_templates）"""
    with db_session_factory() as db:
        basic_id = _seed_basic_available(db, test_settings)
        teacher = _make_user(db, username="t1")
        template = NotebookTemplate(name="N1", owner_id=teacher.id, status="draft")
        db.add(template)
        db.commit()
        db.refresh(template)
        assert template.draft_environment_version_id == basic_id
        assert template.draft_import_policy_mode == "unrestricted"
        assert template.draft_allowed_imports == []


def test_notebook_template_version_binds_environment(db_session_factory, test_settings):
    """发布版本保存不可变环境绑定（plan 4.6 notebook_template_versions）"""
    with db_session_factory() as db:
        basic_id = _seed_basic_available(db, test_settings)
        teacher = _make_user(db, username="t1")
        template = NotebookTemplate(name="N1", owner_id=teacher.id, status="published")
        db.add(template)
        db.commit()
        db.refresh(template)
        version = NotebookTemplateVersion(
            template_id=template.id, version_number=1,
            sha256="s" * 64, cells=[], cell_order=[], notebook_metadata={},
            published_by_id=teacher.id,
        )
        db.add(version)
        db.commit()
        assert version.environment_version_id == basic_id
        assert version.import_policy_mode == "unrestricted"
        assert version.allowed_imports == []


def test_experiment_record_binds_environment(db_session_factory, test_settings):
    """实验记录创建时绑定环境版本（plan 4.6 experiment_records）"""
    from app.models import ExperimentModule

    with db_session_factory() as db:
        basic_id = _seed_basic_available(db, test_settings)
        teacher = _make_user(db, username="t1")
        student = _make_user(db, username="s1")
        template = NotebookTemplate(name="N1", owner_id=teacher.id, status="published")
        db.add(template)
        db.commit()
        db.refresh(template)
        version = NotebookTemplateVersion(
            template_id=template.id, version_number=1,
            sha256="s" * 64, cells=[], cell_order=[], notebook_metadata={},
            published_by_id=teacher.id,
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        # ExperimentRecord 约束：lesson_id 与 module_id 二选一
        module = ExperimentModule(name="M1", template_id=template.id, owner_id=teacher.id)
        db.add(module)
        db.commit()
        db.refresh(module)
        record = ExperimentRecord(
            module_id=module.id, template_version_id=version.id, student_id=student.id
        )
        db.add(record)
        db.commit()
        assert record.environment_version_id == basic_id


def test_no_available_basic_blocks_null_binding(db_session_factory):
    """TASK-010：environment_version_id 为 NOT NULL + 惰性默认绑定 basic 可用版本。

    原「无种子环境时模型层可空」语义已废弃（模型列收紧 NOT NULL），改为断言新契约：
    - 有 basic 可用版本（conftest 预置）：未显式指定环境的作业被默认绑定；
    - 无任何 basic 可用版本：插入 NULL 违反 NOT NULL → IntegrityError。
    """
    with db_session_factory() as db:
        course = Course(title="C1", status="published")
        db.add(course)
        db.commit()
        db.refresh(course)
        assignment = Assignment(course_id=course.id, title="A1", status="draft")
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        basic_id = db.scalar(
            select(EnvironmentVersion.id)
            .join(EnvironmentProfile, EnvironmentProfile.id == EnvironmentVersion.profile_id)
            .where(EnvironmentProfile.slug == "basic", EnvironmentVersion.status == "available")
        )
        assert basic_id is not None, "conftest 应预置 basic 可用版本"
        assert assignment.environment_version_id == basic_id  # NOT NULL + 默认绑定
        assert assignment.import_policy_mode == "unrestricted"
        assert assignment.allowed_imports == []

    with db_session_factory() as db:
        # 移除全部环境行，模拟迁移 B 前无 basic 可用版本的库
        for version in db.query(EnvironmentVersion).all():
            db.delete(version)
        for profile in db.query(EnvironmentProfile).all():
            db.delete(profile)
        db.commit()
        course = Course(title="C2", status="published")
        db.add(course)
        db.commit()
        db.refresh(course)
        assignment = Assignment(course_id=course.id, title="A2", status="draft")
        db.add(assignment)
        with pytest.raises(IntegrityError):  # NOT NULL：无可用版本不得落 NULL
            db.commit()

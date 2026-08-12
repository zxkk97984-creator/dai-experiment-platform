import re

import pytest
from sqlalchemy import func, select

from app.models import (
    Assignment,
    Chapter,
    Course,
    EnvironmentProfile,
    EnvironmentVersion,
    Exam,
    ExperimentModule,
    Lesson,
    NotebookTemplateVersion,
    TeachingClass,
    TeachingClassStudent,
    User,
)
from app.seed_data import (
    TYPICAL_COURSE_TITLE,
    _environment_map,
    seed_internal_test_data,
)


def _seed_environment_catalog(db):
    for index, slug in enumerate(("basic", "data", "torch-cpu"), start=1):
        profile = EnvironmentProfile(
            slug=slug,
            display_name=slug,
            description="seed test environment",
            status="active",
        )
        db.add(profile)
        db.flush()
        db.add(
            EnvironmentVersion(
                profile_id=profile.id,
                version_number=1,
                status="available",
                base_image_ref="python:3.12-slim@sha256:" + "1" * 64,
                image_tag=f"dai-env:{slug}-v1",
                image_digest="sha256:" + str(index) * 64,
                python_version="3.12",
                minimum_memory_mb=256 if slug == "basic" else 768 if slug == "data" else 2048,
                manifest_sha256=str(index) * 64,
            )
        )
    db.commit()


def test_full_seed_has_required_scale_and_is_repeatable(db_session_factory):
    with db_session_factory() as db:
        _seed_environment_catalog(db)
        first = seed_internal_test_data(db, _environment_map(db))
        db.commit()
        second = seed_internal_test_data(db, _environment_map(db))
        db.commit()

        assert first == second
        assert first["teachers"] == 3
        assert first["students"] == 400
        assert first["classes"] == 10
        assert first["courses"] == 30
        assert first["experiment_modules"] == 12

        teachers = db.scalars(select(User).where(User.role == "teacher")).all()
        assert {teacher.username for teacher in teachers} == {
            "teacher_zhang",
            "teacher_chen",
            "teacher_zhao",
        }
        for teacher in teachers:
            assert db.scalar(
                select(func.count()).select_from(Course).where(Course.teacher_id == teacher.id)
            ) == 10

        students = db.scalars(select(User).where(User.role == "student")).all()
        assert len(students) == 400
        assert all(re.fullmatch(r"246216\d{4}", student.student_no or "") for student in students)

        class_counts = db.execute(
            select(TeachingClass.code, func.count(TeachingClassStudent.id))
            .join(TeachingClassStudent, TeachingClassStudent.teaching_class_id == TeachingClass.id)
            .group_by(TeachingClass.id)
        ).all()
        assert len(class_counts) == 10
        assert {count for _, count in class_counts} == {40}

        typical = db.scalar(select(Course).where(Course.title == TYPICAL_COURSE_TITLE))
        assert typical is not None
        assert db.scalar(select(func.count()).select_from(Chapter).where(Chapter.course_id == typical.id)) >= 6
        assert db.scalar(
            select(func.count()).select_from(Lesson).join(Chapter).where(Chapter.course_id == typical.id)
        ) >= 24
        assert db.scalar(select(func.count()).select_from(Assignment).where(Assignment.course_id == typical.id)) >= 10
        assert db.scalar(select(func.count()).select_from(Exam).where(Exam.course_id == typical.id)) >= 10

        assert set(db.scalars(select(Lesson.content_type).distinct()).all()) >= {
            "markdown",
            "video",
            "notebook",
        }
        assert db.scalar(select(func.count()).select_from(ExperimentModule)) >= 12
        assert db.scalar(select(func.count()).select_from(NotebookTemplateVersion)) >= 12


def test_seed_requires_all_available_environments_before_reset(db_session_factory):
    with db_session_factory() as db:
        with pytest.raises(RuntimeError, match="环境控制面尚未完成迁移|以下环境没有可用"):
            _environment_map(db)

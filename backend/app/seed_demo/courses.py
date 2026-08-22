# -*- coding: utf-8 -*-
"""课程 / 章节 / 课时 / 学习进度。

素材复用（只读）：backend/lesson_content/*.md 作为旗舰课程部分 markdown 课时内容。
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AcademicTerm,
    Chapter,
    Course,
    CourseEnrollment,
    CourseWhitelistStudent,
    EnvironmentVersion,
    Lesson,
    LessonProgress,
    NotebookTemplate,
    NotebookTemplateVersion,
    User,
)

from .constants import (
    COURSE_CATALOG,
    COURSE_META,
    FLAGSHIP_COURSE_TITLE,
    WHITELIST_COURSE_STUDENTS,
    WHITELIST_COURSE_TITLE,
)
from .marks import mark
from .rng import make_rng
from .timeline import DemoClock

logger = logging.getLogger("dai.seed_demo.courses")

LESSON_CONTENT_DIR = Path(__file__).resolve().parents[2] / "lesson_content"

# 旗舰课程课时类型模板（每章 4 课时：md / md / notebook / md）
_LESSON_TYPES = [
    ("概念导读", "markdown"),
    ("课堂讲解", "markdown"),
    ("动手实验", "notebook"),
    ("练习与复盘", "markdown"),
]


def _load_lesson_md() -> dict[str, str]:
    """读取 backend/lesson_content/*.md（只读素材），返回 {文件名: 内容}。"""
    result: dict[str, str] = {}
    if not LESSON_CONTENT_DIR.is_dir():
        return result
    for path in sorted(LESSON_CONTENT_DIR.glob("*.md")):
        try:
            result[path.stem] = path.read_text(encoding="utf-8")
        except OSError:
            logger.warning("读取课时素材失败: %s", path)
    return result


def _lesson_markdown(course_title: str, chapter_title: str, suffix: str) -> str:
    """生成结构化课时内容（未命中素材文件时的兜底）。"""
    return (
        f"# {chapter_title}：{suffix}\n\n"
        f"本课时属于课程《{course_title}》。请先阅读概念部分，再完成动手练习。\n\n"
        "## 学习目标\n- 理解本章核心概念\n- 完成代码练习\n- 记录实验结果"
    )


_LESSON_TEMPLATE_ALLOWED_IMPORTS = ["numpy", "matplotlib"]


def _lesson_template_cells(lesson: Lesson) -> list[dict]:
    """课时实验模板的初始 cells：任务说明（markdown）+ 自由练习区（code）。"""
    task_source = (lesson.content or "").strip() or f"# {lesson.title}\n\n按课时要求完成动手实验。"
    return [
        {
            "id": "task",
            "type": "markdown",
            "source": task_source,
            "order": 0,
            "student_editable": False,
            "source_hidden": False,
        },
        {
            "id": "scratch",
            "type": "code",
            "source": "# 动手实验：在下方编写并运行你的代码\nprint(\"Hello, DAI!\")\n",
            "order": 1,
            "student_editable": True,
            "source_hidden": False,
        },
    ]


def _bind_lesson_notebook_template(
    db: Session, course: Course, lesson: Lesson, env_version: EnvironmentVersion | None
) -> None:
    """为 notebook 课时创建并绑定已发布模板；幂等，可修复存量未绑定课时。"""
    if lesson.content_type != "notebook":
        return
    if lesson.template_id is not None:
        return
    if env_version is None:
        logger.warning("[跳过] 课时 %s 缺 basic 环境，无法创建 Notebook 模板", lesson.id)
        return

    template_name = f"课时实验：{course.title} · {lesson.title}"
    template = db.scalar(select(NotebookTemplate).where(NotebookTemplate.name == template_name))
    if template is None:
        cells = _lesson_template_cells(lesson)
        digest = hashlib.sha256(
            json.dumps(cells, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        template = NotebookTemplate(
            name=template_name,
            description=f"《{course.title}》课时「{lesson.title}」的动手实验模板",
            status="published",
            owner_id=course.teacher_id,
            draft_cells=cells,
            draft_revision=1,
            draft_metadata={"seed": True},
            draft_assets_dir=None,
            draft_environment_version_id=env_version.id,
            draft_import_policy_mode="restricted",
            draft_allowed_imports=_LESSON_TEMPLATE_ALLOWED_IMPORTS,
        )
        db.add(template)
        db.flush()
        version = NotebookTemplateVersion(
            template_id=template.id,
            version_number=1,
            sha256=digest,
            cells=cells,
            cell_order=[cell["id"] for cell in cells],
            notebook_metadata={"seed": True},
            assets_dir=None,
            published_by_id=course.teacher_id,
            environment_version_id=env_version.id,
            import_policy_mode="restricted",
            allowed_imports=_LESSON_TEMPLATE_ALLOWED_IMPORTS,
        )
        db.add(version)
        db.flush()
        template.current_version_id = version.id
        db.flush()
        mark(db, "notebook_templates", template.id)
        mark(db, "notebook_template_versions", version.id)
        logger.info("[创建] 课时 Notebook 模板 %s", template_name)
    elif template.current_version_id is None:
        logger.warning("[跳过] 模板 %s 无可用版本，课时 %s 保持未绑定", template_name, lesson.id)
        return

    lesson.template_id = template.id
    db.flush()
    logger.info("[绑定] 课时 %s → Notebook 模板 %s", lesson.id, template_name)


def create_courses(
    db: Session, clock: DemoClock, users: dict, term: AcademicTerm,
    env_by_slug: dict | None = None,
) -> dict:
    """创建课程/章节/课时；返回 {title: Course}。

    env_by_slug：可选；提供时为 notebook 课时创建并绑定 Notebook 模板（含存量课时修复）。
    """
    lesson_md = _load_lesson_md()
    courses: dict[str, Course] = {}
    md_index = 0

    for title, teacher_key, env_slug, status, topics in COURSE_CATALOG:
        teacher = users[teacher_key]
        meta = COURSE_META.get(title, {})
        visibility = meta.get("visibility", "class")
        start_time = clock.day(meta.get("start_offset_days", -90), 9) if status == "published" else None
        course = db.scalar(select(Course).where(Course.title == title))
        if course is None:
            course = Course(
                title=title,
                code=meta.get("code"),
                description=(
                    f"《{title}》——Demo 演示课程，覆盖章节、课时、作业与考试全流程。"
                    if title == FLAGSHIP_COURSE_TITLE
                    else (
                        "《AI 创新实践（白名单）》——仅对白名单学生可见的选修课，"
                        "用于验证课程可见性、白名单管理与选课权限。"
                        if title == WHITELIST_COURSE_TITLE
                        else f"《{title}》——Demo 支撑课程，用于教学班与课程管理演示。"
                    )
                ),
                status=status,
                teacher_id=teacher.id,
                academic_term_id=term.id,
                visibility=visibility,
                cover=meta.get("cover"),
                start_time=start_time,
                default_score=100.0,
            )
            db.add(course)
            db.flush()
            logger.info("[创建] 课程 %s", title)
        else:
            course.status = status
            course.teacher_id = teacher.id
            course.visibility = visibility
            if meta.get("code"):
                course.code = meta["code"]
            if meta.get("cover"):
                course.cover = meta["cover"]
            if start_time is not None:
                course.start_time = start_time
            if course.academic_term_id is None:
                course.academic_term_id = term.id
            db.flush()
            logger.info("[更新] 课程 %s", title)
        mark(db, "courses", course.id)
        courses[title] = course

        # 章节
        for chapter_index, topic in enumerate(topics):
            chapter = db.scalar(
                select(Chapter).where(
                    Chapter.course_id == course.id,
                    Chapter.title == f"第{chapter_index + 1}章 {topic}",
                )
            )
            if chapter is None:
                chapter = Chapter(
                    course_id=course.id,
                    title=f"第{chapter_index + 1}章 {topic}",
                    order_index=chapter_index,
                )
                db.add(chapter)
                db.flush()
                logger.info("[创建] 章节 %s/%s", title, chapter.title)
            mark(db, "chapters", chapter.id)

            # 课时
            lesson_count = 4 if title == FLAGSHIP_COURSE_TITLE else 3
            for lesson_index in range(lesson_count):
                suffix, content_type = _LESSON_TYPES[lesson_index % 4]
                lesson_title = f"{topic}：{suffix}"
                lesson = db.scalar(
                    select(Lesson).where(
                        Lesson.chapter_id == chapter.id,
                        Lesson.title == lesson_title,
                    )
                )
                if lesson is None:
                    # 旗舰课程 markdown 课时复用 lesson_content 素材
                    content = None
                    if title == FLAGSHIP_COURSE_TITLE and content_type == "markdown":
                        stems = sorted(lesson_md.keys())
                        if stems:
                            content = lesson_md[stems[md_index % len(stems)]]
                            md_index += 1
                    if content is None:
                        content = _lesson_markdown(title, topic, suffix)
                    lesson = Lesson(
                        chapter_id=chapter.id,
                        title=lesson_title,
                        content_type=content_type,
                        content=content,
                        order_index=lesson_index,
                        status="published",
                    )
                    db.add(lesson)
                    db.flush()
                    logger.info("[创建] 课时 %s/%s", title, lesson_title)
                else:
                    lesson.status = "published"
                    db.flush()
                if env_by_slug:
                    _bind_lesson_notebook_template(
                        db, course, lesson, env_by_slug.get("basic")
                    )
                mark(db, "lessons", lesson.id)
        db.flush()
    return courses


def create_course_whitelists(
    db: Session, users: dict, courses: dict,
) -> None:
    """为白名单课程创建可见学生白名单，并为其中一名学生建立 manual 选课。

    白名单课程不绑定教学班：白名单决定“能否发现”，选课决定“能否访问内容”。
    - elite：白名单 + manual 选课（可完整访问课程内容）
    - average / new：仅白名单（可发现、可申请选课，但尚未选课）
    - struggling：不在白名单（权限负例，不应在课程列表看到该课程）
    """
    course = courses.get(WHITELIST_COURSE_TITLE)
    if course is None:
        return
    for username in WHITELIST_COURSE_STUDENTS:
        student = users.get(username)
        if student is None:
            continue
        existing = db.scalar(
            select(CourseWhitelistStudent).where(
                CourseWhitelistStudent.course_id == course.id,
                CourseWhitelistStudent.student_id == student.id,
            )
        )
        if existing is None:
            existing = CourseWhitelistStudent(course_id=course.id, student_id=student.id)
            db.add(existing)
            db.flush()
            logger.info("[创建] 课程白名单 %s -> %s", course.title, username)
        mark(db, "course_whitelist_students", existing.id)

    # elite 已选课，能访问白名单课程内容；其余仅可发现
    elite = users.get("demo_student_elite")
    if elite is not None:
        enrollment = db.scalar(
            select(CourseEnrollment).where(
                CourseEnrollment.course_id == course.id,
                CourseEnrollment.student_id == elite.id,
            )
        )
        if enrollment is None:
            enrollment = CourseEnrollment(
                course_id=course.id,
                student_id=elite.id,
                status="enrolled",
                origin="manual",
            )
            db.add(enrollment)
            db.flush()
            logger.info("[创建] 白名单课程选课 %s -> %s", course.title, elite.username)
        mark(db, "course_enrollments", enrollment.id)
    db.flush()


def create_lesson_progress(
    db: Session, clock: DemoClock, users: dict, courses: dict,
) -> None:
    """为学生创建课时学习进度（lesson_progress）。

    画像学生按画像完成度；背景学生按固定种子抽样。只覆盖旗舰课程课时。
    """
    from .constants import ARCHETYPES, BACKGROUND_ARCHETYPE, FIXED_STUDENT_DEFS

    flagship = courses[FLAGSHIP_COURSE_TITLE]
    lessons = list(
        db.scalars(
            select(Lesson).join(Chapter, Chapter.id == Lesson.chapter_id)
            .where(Chapter.course_id == flagship.id)
            .order_by(Chapter.order_index, Lesson.order_index)
        ).all()
    )
    if not lessons:
        return

    archetype_map = {uname: a for uname, _n, a in FIXED_STUDENT_DEFS}
    for student in users["students"]:
        archetype_key = archetype_map.get(student.username, BACKGROUND_ARCHETYPE)
        profile = ARCHETYPES[archetype_key]
        rng = make_rng("progress", student.username)
        total = len(lessons)
        complete_count = max(1, int(round(total * profile["lesson_complete"])))
        for lesson in lessons[:complete_count]:
            existing = db.scalar(
                select(LessonProgress).where(
                    LessonProgress.lesson_id == lesson.id,
                    LessonProgress.student_id == student.id,
                )
            )
            if existing is not None:
                mark(db, "lesson_progress", existing.id)
                continue
            row = LessonProgress(
                lesson_id=lesson.id,
                student_id=student.id,
                status="completed",
                last_accessed_at=_random_lesson_time(clock, rng),
            )
            db.add(row)
            db.flush()
            mark(db, "lesson_progress", row.id)
    db.flush()


def _random_lesson_time(clock: DemoClock, rng):
    """在学期窗口内随机生成一个（早于参考日期）的学习时间。"""
    from datetime import timedelta

    start, end = clock.experiment_activity_window()
    span = (end - start).total_seconds()
    return start + timedelta(seconds=rng.uniform(0, span))

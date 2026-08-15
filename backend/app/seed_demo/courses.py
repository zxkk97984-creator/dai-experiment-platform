# -*- coding: utf-8 -*-
"""课程 / 章节 / 课时 / 学习进度。

素材复用（只读）：backend/lesson_content/*.md 作为旗舰课程部分 markdown 课时内容。
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AcademicTerm, Chapter, Course, Lesson, LessonProgress, User

from .constants import COURSE_CATALOG, FLAGSHIP_COURSE_TITLE
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


def create_courses(
    db: Session, clock: DemoClock, users: dict, term: AcademicTerm,
) -> dict:
    """创建课程/章节/课时；返回 {title: Course}。"""
    lesson_md = _load_lesson_md()
    courses: dict[str, Course] = {}
    md_index = 0

    for title, teacher_key, env_slug, status, topics in COURSE_CATALOG:
        teacher = users[teacher_key]
        course = db.scalar(select(Course).where(Course.title == title))
        if course is None:
            course = Course(
                title=title,
                description=(
                    f"《{title}》——Demo 演示课程，覆盖章节、课时、作业与考试全流程。"
                    if title == FLAGSHIP_COURSE_TITLE
                    else f"《{title}》——Demo 支撑课程，用于教学班与课程管理演示。"
                ),
                status=status,
                teacher_id=teacher.id,
                academic_term_id=term.id,
                visibility="class",
                default_score=100.0,
            )
            db.add(course)
            db.flush()
            logger.info("[创建] 课程 %s", title)
        else:
            course.status = status
            course.teacher_id = teacher.id
            course.visibility = "class"
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
                mark(db, "lessons", lesson.id)
        db.flush()
    return courses


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

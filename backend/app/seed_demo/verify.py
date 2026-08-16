# -*- coding: utf-8 -*-
"""播种后校验：表计数、外键抽查、状态分布、幂等断言（评审 3.7）。"""
from __future__ import annotations

import logging

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import (
    AcademicTerm,
    Announcement,
    Assignment,
    Chapter,
    CodeGrade,
    Course,
    CourseEnrollment,
    CourseWhitelistStudent,
    Exam,
    ExamAnswer,
    ExamQuestion,
    ExamSubmission,
    ExperimentModule,
    ExperimentRecord,
    ExperimentSubmission,
    JudgeQuestion,
    Lesson,
    LessonProgress,
    NotebookTemplate,
    NotebookTemplateVersion,
    QuestionRubric,
    Submission,
    TeachingClass,
    TeachingClassStudent,
    User,
)

logger = logging.getLogger("dai.seed_demo.verify")


def count(db: Session, model) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def verify_demo_data(db: Session) -> dict:
    """运行播种后校验；返回各表计数。失败抛 RuntimeError。"""
    counts = {
        "users": count(db, User),
        "academic_terms": count(db, AcademicTerm),
        "teaching_classes": count(db, TeachingClass),
        "teaching_class_students": count(db, TeachingClassStudent),
        "courses": count(db, Course),
        "chapters": count(db, Chapter),
        "lessons": count(db, Lesson),
        "course_enrollments": count(db, CourseEnrollment),
        "course_whitelist_students": count(db, CourseWhitelistStudent),
        "lesson_progress": count(db, LessonProgress),
        "assignments": count(db, Assignment),
        "judge_questions": count(db, JudgeQuestion),
        "submissions": count(db, Submission),
        "exams": count(db, Exam),
        "exam_questions": count(db, ExamQuestion),
        "exam_submissions": count(db, ExamSubmission),
        "exam_answers": count(db, ExamAnswer),
        "notebook_templates": count(db, NotebookTemplate),
        "notebook_template_versions": count(db, NotebookTemplateVersion),
        "experiment_modules": count(db, ExperimentModule),
        "experiment_records": count(db, ExperimentRecord),
        "experiment_submissions": count(db, ExperimentSubmission),
        "question_rubrics": count(db, QuestionRubric),
        "code_grades": count(db, CodeGrade),
        "announcements": count(db, Announcement),
    }

    errors: list[str] = []
    # 基础断言：核心实体必须存在
    if counts["users"] < 65:
        errors.append(f"用户数不足 65：{counts['users']}")
    if counts["courses"] < 8:
        errors.append(f"课程数不足 8：{counts['courses']}")
    if counts["course_whitelist_students"] < 3:
        errors.append(f"课程白名单数不足 3：{counts['course_whitelist_students']}")
    if counts["assignments"] < 9:
        errors.append(f"作业数不足 9：{counts['assignments']}")
    if counts["submissions"] < 200:
        errors.append(f"提交数不足 200：{counts['submissions']}")
    if counts["exams"] < 3:
        errors.append(f"考试数不足 3：{counts['exams']}")
    if counts["code_grades"] < 100:
        errors.append(f"AI 评分记录不足 100：{counts['code_grades']}")

    # 状态抽查：真实/Fixture 判题都不应残留 system_error
    # （技术债修复：占位 digest / Docker 级失败必须降级 Fixture，不得写坏状态）
    syserr = db.scalar(
        select(func.count()).select_from(Submission).where(Submission.status == "system_error")
    ) or 0
    if syserr:
        errors.append(f"存在 {syserr} 条 system_error 提交（判题降级链路异常）")

    # 唯一键抽查：用户名无重复
    dup = db.execute(
        text("SELECT username, COUNT(*) c FROM users GROUP BY username HAVING c > 1")
    ).all()
    if dup:
        errors.append(f"用户名重复: {dup}")

    # 白名单课程必须存在且仅白名单学生可见（权限场景）
    whitelist_course = db.scalar(
        select(Course).where(Course.title == "AI 创新实践（白名单）")
    )
    if whitelist_course is None:
        errors.append("缺少白名单课程：AI 创新实践（白名单）")
    else:
        if whitelist_course.visibility != "whitelist":
            errors.append("白名单课程 visibility 不是 whitelist")
        if whitelist_course.status != "published":
            errors.append("白名单课程未发布")

    # 外键抽查：随机查询存在性
    orphan = db.execute(
        text("SELECT COUNT(*) FROM lessons l LEFT JOIN chapters c ON l.chapter_id = c.id WHERE c.id IS NULL")
    ).scalar()
    if orphan:
        errors.append(f"课时存在悬空章节引用: {orphan}")

    if errors:
        raise RuntimeError("Demo 数据校验失败: " + "; ".join(errors))
    return counts

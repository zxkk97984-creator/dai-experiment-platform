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
    CourseTeachingClass,
    CourseWhitelistStudent,
    EnvironmentBuildJob,
    EnvironmentVersion,
    Exam,
    ExamAnswer,
    ExamGrade,
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
    StorageObject,
    TeachingClass,
    TeachingClassStudent,
    User,
)
from .marks import all_marks

logger = logging.getLogger("dai.seed_demo.verify")


MARKED_MODELS = {
    "users": User,
    "academic_terms": AcademicTerm,
    "teaching_classes": TeachingClass,
    "teaching_class_students": TeachingClassStudent,
    "course_teaching_classes": CourseTeachingClass,
    "courses": Course,
    "chapters": Chapter,
    "lessons": Lesson,
    "course_enrollments": CourseEnrollment,
    "course_whitelist_students": CourseWhitelistStudent,
    "lesson_progress": LessonProgress,
    "assignments": Assignment,
    "judge_questions": JudgeQuestion,
    "submissions": Submission,
    "question_rubrics": QuestionRubric,
    "code_grades": CodeGrade,
    "exams": Exam,
    "exam_questions": ExamQuestion,
    "exam_submissions": ExamSubmission,
    "exam_answers": ExamAnswer,
    "notebook_templates": NotebookTemplate,
    "notebook_template_versions": NotebookTemplateVersion,
    "experiment_modules": ExperimentModule,
    "experiment_records": ExperimentRecord,
    "experiment_submissions": ExperimentSubmission,
    "announcements": Announcement,
    "announcement_reads": None,  # no standalone ORM model is needed here
}


def count(db: Session, model) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def verify_demo_data(db: Session) -> dict:
    """运行播种后校验；返回各表计数。失败抛 RuntimeError。"""
    marks = all_marks(db)
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
        "exam_grades": count(db, ExamGrade),
        "notebook_templates": count(db, NotebookTemplate),
        "notebook_template_versions": count(db, NotebookTemplateVersion),
        "experiment_modules": count(db, ExperimentModule),
        "experiment_records": count(db, ExperimentRecord),
        "experiment_submissions": count(db, ExperimentSubmission),
        "question_rubrics": count(db, QuestionRubric),
        "code_grades": count(db, CodeGrade),
        "announcements": count(db, Announcement),
        "storage_objects": count(db, StorageObject),
        "environment_versions": count(db, EnvironmentVersion),
        "environment_build_jobs": count(db, EnvironmentBuildJob),
    }

    errors: list[str] = []
    # 基础断言：核心实体必须存在
    if counts["users"] < 64:
        errors.append(f"用户数不足 64：{counts['users']}")
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

    # Demo 用户角色闭集：只检查本次登记的 Demo 用户，不误伤同库中的其他租户/测试用户。
    demo_user_ids = marks.get("users", [])
    if demo_user_ids:
        invalid_roles = db.execute(
            select(User.username, User.role)
            .where(User.id.in_(demo_user_ids), ~User.role.in_(("student", "teacher", "admin")))
        ).all()
        if invalid_roles:
            errors.append(f"Demo 用户存在非法角色: {invalid_roles}")

    # 所有权登记必须可追溯：未知表名或已被外部删除的标记一律报警，防止
    # reset-demo 静默漏删/误删。announcement_reads 是派生表，使用专门查询。
    for table_name, row_ids in marks.items():
        if table_name not in MARKED_MODELS:
            errors.append(f"demo_seed_marks 存在未允许的表: {table_name}")
            continue
        if table_name == "announcement_reads":
            if row_ids:
                placeholders = ",".join(f":id{i}" for i in range(len(row_ids)))
                existing = {
                    int(row[0])
                    for row in db.execute(
                        text(f"SELECT id FROM announcement_reads WHERE id IN ({placeholders})"),
                        {f"id{i}": value for i, value in enumerate(row_ids)},
                    ).all()
                }
                missing = sorted(set(row_ids) - existing)
                if missing:
                    errors.append(f"Demo 标记引用不存在的 announcement_reads: {missing[:10]}")
            continue
        model = MARKED_MODELS[table_name]
        if model is None or not row_ids:
            continue
        existing_ids = set(
            db.scalars(select(model.id).where(model.id.in_(row_ids))).all()
        )
        missing = sorted(set(row_ids) - existing_ids)
        if missing:
            errors.append(f"Demo 标记引用不存在的 {table_name}: {missing[:10]}")

    # Seed 不生成上传型文件：封面使用明确的 data URI 兼容数据，Notebook/实验
    # 内容写入 JSON 字段，Studio 目录字段保持空值；因此本轮不应新增 StorageObject。
    # 非 Demo 的既有 StorageObject 不参与此断言，也不会被 reset-demo 触碰。
    if marks.get("storage_objects"):
        errors.append("当前 Demo seed 不应登记 StorageObject 上传文件")

    # 环境控制面只做状态不变量校验，不创建/修复环境数据。
    succeeded_with_error = db.scalar(
        select(func.count()).select_from(EnvironmentBuildJob).where(
            EnvironmentBuildJob.status == "succeeded",
            (EnvironmentBuildJob.error_code.is_not(None) | EnvironmentBuildJob.error_message.is_not(None)),
        )
    ) or 0
    if succeeded_with_error:
        errors.append(f"存在 {succeeded_with_error} 条 succeeded 但残留错误的环境任务")
    available_without_digest = db.scalar(
        select(func.count()).select_from(EnvironmentVersion).where(
            EnvironmentVersion.status == "available",
            EnvironmentVersion.image_digest.is_(None),
        )
    ) or 0
    if available_without_digest:
        errors.append(f"存在 {available_without_digest} 个 available 但无 image_digest 的环境版本")
    queued_without_job = db.scalar(
        select(func.count()).select_from(EnvironmentVersion).where(
            EnvironmentVersion.status == "queued",
            ~select(EnvironmentBuildJob.id).where(
                EnvironmentBuildJob.environment_version_id == EnvironmentVersion.id,
                EnvironmentBuildJob.status.in_(("queued", "building")),
            ).exists(),
        )
    ) or 0
    if queued_without_job:
        errors.append(f"存在 {queued_without_job} 个 queued 环境版本没有活动构建任务")

    # 状态抽查：真实/Fixture 判题都不应残留 system_error
    # （技术债修复：占位 digest / Docker 级失败必须降级 Fixture，不得写坏状态）
    demo_submission_ids = marks.get("submissions", [])
    syserr = db.scalar(
        select(func.count()).select_from(Submission).where(
            Submission.id.in_(demo_submission_ids),
            Submission.status == "system_error",
        )
    ) or 0
    if syserr:
        errors.append(f"存在 {syserr} 条 system_error 提交（判题降级链路异常）")

    demo_exam_answer_ids = marks.get("exam_answers", [])
    exam_syserr = db.scalar(
        select(func.count()).select_from(ExamAnswer).where(
            ExamAnswer.id.in_(demo_exam_answer_ids),
            ExamAnswer.grading_status == "system_error",
        )
    ) or 0
    if exam_syserr:
        errors.append(f"存在 {exam_syserr} 条 system_error 考试答案（不得生成 ExamGrade）")

    demo_exam_submission_ids = marks.get("exam_submissions", [])
    grade_missing = db.scalar(
        select(func.count()).select_from(ExamSubmission).where(
            ExamSubmission.id.in_(demo_exam_submission_ids),
            ExamSubmission.status == "graded",
            ExamSubmission.score.is_not(None),
            ~select(ExamGrade.id).where(
                ExamGrade.exam_id == ExamSubmission.exam_id,
                ExamGrade.student_id == ExamSubmission.student_id,
            ).exists(),
        )
    ) or 0
    if grade_missing:
        errors.append(f"存在 {grade_missing} 条 graded 考试提交没有 ExamGrade 汇总")

    review_with_grade = db.scalar(
        select(func.count()).select_from(ExamSubmission)
        .join(
            ExamGrade,
            (ExamGrade.exam_id == ExamSubmission.exam_id)
            & (ExamGrade.student_id == ExamSubmission.student_id),
        )
        .where(
            ExamSubmission.id.in_(demo_exam_submission_ids),
            ExamSubmission.status == "review_required",
        )
    ) or 0
    if review_with_grade:
        errors.append(f"存在 {review_with_grade} 条 review_required 提交错误生成 ExamGrade")

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

    demo_course_ids = marks.get("courses", [])
    course_teacher_errors = db.scalar(
        select(func.count())
        .select_from(Course)
        .join(User, User.id == Course.teacher_id)
        .where(Course.id.in_(demo_course_ids), User.role != "teacher")
    ) or 0
    if course_teacher_errors:
        errors.append(f"存在 {course_teacher_errors} 门课程未由 teacher 负责")

    if errors:
        raise RuntimeError("Demo 数据校验失败: " + "; ".join(errors))
    return counts

# -*- coding: utf-8 -*-
"""--reset-demo：仅按 demo_seed_marks 登记删除（评审 3）。

所有权以登记表为准：未登记业务行绝不删除（即使用户手动给 Demo 题目提交过）。
按外键拓扑逆序分批 DELETE，只对登记过的 (table_name, row_id) 执行；
外键阻断（未登记子行引用 Demo 行）时整体回滚并报告，绝不部分删除。

例外：
- 站内通知 / 通知已读 / 用户偏好属于 API 使用过程中自动产生的运行态数据，
  不是用户手工业务数据；重置时会一并清理“引用 Demo 用户”的这些行。
- grade_overrides 是教师对 Demo 成绩的复核/改分审计；若不清理会永久阻塞
  code_grades 删除，导致 --reset-demo 无法工作。重置时仅清理“引用已登记
  Demo code_grades”的改分审计，不触碰其他非 Demo 改分记录。
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from .marks import all_marks, clear_marks, ensure_marks_table

logger = logging.getLogger("dai.seed_demo.cleanup")

# 删除顺序：子表先于父表（外键拓扑逆序）。
# 依据 app/models/__init__.py 的外键定义核对：
# - code_grades -> submissions/exam_answers/question_rubrics
# - question_rubrics -> judge_questions/exam_questions
# - course_enrollments/course_teaching_classes -> courses
# - teaching_class_students -> teaching_classes；lessons -> chapters -> courses
DELETE_ORDER = [
    "grade_overrides",              # -> code_grades, users
    "code_grades",                  # -> submissions/exam_answers, question_rubrics
    "question_rubrics",             # -> judge_questions/exam_questions
    "submissions",                  # -> judge_questions, users, environment_versions
    "exam_answers",                 # -> exam_submissions, exam_questions
    "exam_submissions",             # -> exams, users
    "experiment_submissions",       # -> experiment_records, users
    "experiment_records",           # -> lessons/modules, notebook_template_versions, users
    "lesson_progress",              # -> lessons, users
    "course_whitelist_students",    # -> courses, users
    "announcement_reads",           # -> announcements, users
    "announcements",                # -> courses, users
    "experiment_modules",           # -> notebook_templates, users
    "lessons",                      # -> chapters, notebook_templates
    "judge_questions",              # -> assignments
    "exam_questions",               # -> exams
    "assignments",                  # -> courses, users
    "exams",                        # -> courses, users
    "chapters",                     # -> courses
    "course_enrollments",           # -> courses, users
    "course_teaching_classes",      # -> courses, teaching_classes
    "courses",                      # -> users, academic_terms
    "teaching_class_students",      # -> teaching_classes, users
    "teaching_classes",             # -> academic_terms
    "academic_terms",               # -> (none)
    "notebook_template_versions",   # -> notebook_templates, users
    "notebook_templates",           # -> users
    "users",                        # -> (none)
]


def _delete_derived_system_rows(db: Session, marks: dict[str, list[int]]) -> int:
    """清理 API 自动产生的、引用 Demo 用户的运行态数据。

    这些表不由 seed 直接创建，因此不在 demo_seed_marks 中；但它们会因调用
    /notifications、/users/me/preferences 等接口而出现，若不清理会阻塞 users 删除。
    """
    user_ids = marks.get("users", [])
    if not user_ids:
        return 0
    placeholders = ",".join(f":uid{j}" for j in range(len(user_ids)))
    params = {f"uid{j}": uid for j, uid in enumerate(user_ids)}
    total = 0

    # 通知已读：先删“这些通知的被读记录”，再删“这些用户的已读记录”
    result = db.execute(
        text(
            "DELETE FROM notification_reads WHERE notification_id IN ("
            "  SELECT id FROM notifications WHERE recipient_id IN (" + placeholders + ")"
            ")"
        ),
        params,
    )
    total += result.rowcount or 0
    result = db.execute(
        text(f"DELETE FROM notification_reads WHERE user_id IN ({placeholders})"),
        params,
    )
    total += result.rowcount or 0

    result = db.execute(
        text(f"DELETE FROM notifications WHERE recipient_id IN ({placeholders})"),
        params,
    )
    total += result.rowcount or 0

    result = db.execute(
        text(f"DELETE FROM user_preferences WHERE user_id IN ({placeholders})"),
        params,
    )
    total += result.rowcount or 0
    return total


def _delete_dependent_audit_rows(db: Session, marks: dict[str, list[int]]) -> int:
    """清理引用 Demo code_grades 的教师改分审计（grade_overrides）。

    这些行不是 seed 直接创建的，但不清理会导致删除 code_grades 时外键阻断，
    使 --reset-demo 在测试过“教师改分”后无法重复初始化。
    """
    code_grade_ids = marks.get("code_grades", [])
    if not code_grade_ids:
        return 0
    total = 0
    for i in range(0, len(code_grade_ids), 200):
        chunk = code_grade_ids[i : i + 200]
        placeholders = ",".join(f":id{j}" for j in range(len(chunk)))
        params = {f"id{j}": rid for j, rid in enumerate(chunk)}
        result = db.execute(
            text(f"DELETE FROM grade_overrides WHERE code_grade_id IN ({placeholders})"),
            params,
        )
        total += result.rowcount or 0
    return total


def reset_demo_data(db: Session) -> int:
    """删除所有登记过的 Demo 数据；返回删除行数。若外键阻断则回滚并抛异常。"""
    ensure_marks_table(db)
    marks = all_marks(db)
    total = 0
    blocked: list[str] = []

    try:
        total += _delete_derived_system_rows(db, marks)
        total += _delete_dependent_audit_rows(db, marks)
        # 先断开 notebook_templates 的循环外键（current_version_id）——
        # 仅对登记过的 Demo 模板置空，不触碰非 Demo 模板
        tmpl_ids = marks.get("notebook_templates", [])
        if tmpl_ids:
            placeholders = ",".join(f":id{j}" for j in range(len(tmpl_ids)))
            params = {f"id{j}": rid for j, rid in enumerate(tmpl_ids)}
            db.execute(
                text(
                    "UPDATE notebook_templates SET current_version_id = NULL"
                    f" WHERE id IN ({placeholders})"
                ),
                params,
            )

        for table in DELETE_ORDER:
            ids = marks.get(table, [])
            if not ids:
                continue
            # 分片删除，避免超长 IN 列表
            for i in range(0, len(ids), 200):
                chunk = ids[i : i + 200]
                placeholders = ",".join(f":id{j}" for j in range(len(chunk)))
                params = {f"id{j}": rid for j, rid in enumerate(chunk)}
                try:
                    result = db.execute(
                        text(f"DELETE FROM {table} WHERE id IN ({placeholders})"),
                        params,
                    )
                    total += result.rowcount or 0
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    blocked.append(f"{table}({len(chunk)} ids): {exc}")
                    raise RuntimeError(
                        "Demo 数据删除被外键阻断，已整体回滚。请先处理引用 Demo 数据的"
                        f"非 Demo 记录。阻断详情: {'; '.join(blocked)}"
                    ) from exc
        clear_marks(db)
        db.commit()
        logger.info("[reset-demo] 已删除 %d 行 Demo 数据", total)
        return total
    except Exception:
        db.rollback()
        raise

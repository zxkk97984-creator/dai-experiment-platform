"""E2E 种子数据——直接通过模型插入，绕过 API 认证。

幂等：按唯一标识（用户名/标题）检查，已存在则复用并跳过创建，可安全重复执行。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models import (
    User, Course, CourseEnrollment, Chapter, Lesson,
    Assignment, JudgeQuestion, Exam, ExamQuestion, ExamSubmission, ExamAnswer,
    ExperimentModule, ExperimentRecord, ExperimentSubmission,
    NotebookTemplate, NotebookTemplateVersion,
)
from app.security import hash_password
from datetime import datetime, timezone

db = SessionLocal()
now = datetime.now(timezone.utc)


def get_or_create(model, created_msg, **fields):
    """按 fields 中的唯一标识查询，存在则复用，不存在则创建并 flush。"""
    identity = {k: v for k, v in fields.items() if k in ("username", "title", "name")}
    obj = db.query(model).filter_by(**identity).first() if identity else None
    if obj:
        print(f"  [跳过] {created_msg}")
        return obj
    obj = model(**fields)
    db.add(obj)
    db.flush()
    print(f"  [创建] {created_msg} id={obj.id}")
    return obj


try:
    # ── 1. 用户（已存在则跳过；admin 密码以现有数据库为准） ──
    print("1. 用户")
    admin = get_or_create(User, "admin", username="admin", real_name="管理员",
                          role="admin", status="active",
                          password_hash=hash_password("Passw0rd!"))
    teacher = get_or_create(User, "teacher", username="teacher", real_name="测试教师",
                            role="teacher", status="active",
                            password_hash=hash_password("Passw0rd!"))
    student = get_or_create(User, "student", username="student", real_name="测试学生",
                            role="student", status="active",
                            password_hash=hash_password("Passw0rd!"))

    # ── 2. 课程 ──
    print("2. 课程")
    course = get_or_create(Course, "E2E 测试课程",
                           title="E2E 测试课程", description="Playwright E2E",
                           status="published", teacher_id=teacher.id)
    cid = course.id

    # ── 3. 选课（同一课程+学生已选则跳过） ──
    print("3. 学生选课")
    enroll = db.query(CourseEnrollment).filter_by(course_id=cid, student_id=student.id).first()
    if not enroll:
        db.add(CourseEnrollment(course_id=cid, student_id=student.id, status="enrolled"))
        db.flush()
        print(f"  [创建] 选课 course={cid} student={student.id}")
    else:
        print("  [跳过] 选课")

    # ── 4. 章节 + 课时 ──
    print("4. 章节和课时")
    chapter = db.query(Chapter).filter_by(course_id=cid, title="第一章").first()
    if not chapter:
        chapter = Chapter(course_id=cid, title="第一章", order_index=1)
        db.add(chapter)
        db.flush()
        print(f"  [创建] 章节 id={chapter.id}")
    lesson = db.query(Lesson).filter_by(chapter_id=chapter.id, title="第一课").first()
    if not lesson:
        lesson = Lesson(chapter_id=chapter.id, title="第一课", content_type="markdown",
                        content="# 测试课时", order_index=1)
        db.add(lesson)
        db.flush()
        print(f"  [创建] 课时 id={lesson.id}")

    # ── 5. 作业 + 判题题目 ──
    print("5. 作业和判题题目")
    assignment = db.query(Assignment).filter_by(course_id=cid, title="E2E 测试作业").first()
    if not assignment:
        assignment = Assignment(course_id=cid, title="E2E 测试作业", status="published")
        db.add(assignment)
        db.flush()
        print(f"  [创建] 作业 id={assignment.id}")
    question = db.query(JudgeQuestion).filter_by(assignment_id=assignment.id, title="加法函数").first()
    if not question:
        question = JudgeQuestion(
            assignment_id=assignment.id,
            title="加法函数", function_name="add",
            public_cases=[{"args": [1, 2], "expected": 3}],
            hidden_tests="import user_code\n\ndef test_hidden():\n    assert user_code.add(1, 2) == 3\n",
            time_limit_ms=10000, memory_limit_mb=256,
        )
        db.add(question)
        db.flush()
        print(f"  [创建] 题目 id={question.id}")

    # ── 6. 考试 ──
    print("6. 考试")
    exam = db.query(Exam).filter_by(course_id=cid, title="E2E 测试考试").first()
    if not exam:
        exam = Exam(course_id=cid, title="E2E 测试考试", status="published",
                    duration_minutes=60)
        db.add(exam)
        db.flush()
        print(f"  [创建] 考试 id={exam.id}")
    eq = db.query(ExamQuestion).filter_by(exam_id=exam.id, prompt="1+1=?").first()
    if not eq:
        eq = ExamQuestion(
            exam_id=exam.id, question_type="single_choice",
            prompt="1+1=?",
            options={"A": "1", "B": "2", "C": "3", "D": "4"},
            correct_answer={"correct": ["B"]},
            points=10, order_index=1,
        )
        db.add(eq)
        db.flush()
        print(f"  [创建] 考试题目 id={eq.id}")

    # ── 7. Notebook Template + 实验模块 ──
    print("7. Notebook Template 和实验模块")
    tpl = db.query(NotebookTemplate).filter_by(name="E2E 测试模板").first()
    if not tpl:
        tpl = NotebookTemplate(name="E2E 测试模板", description="E2E",
                               status="published", owner_id=teacher.id,
                               draft_cells=[], draft_revision=1)
        db.add(tpl)
        db.flush()
        print(f"  [创建] 模板 id={tpl.id}")

        version = NotebookTemplateVersion(
            template_id=tpl.id, version_number=1, sha256="e2e-seed-sha",
            cells=[{"id": "c1", "type": "code", "source": "print('hello e2e')",
                    "order": 0, "student_editable": True, "source_hidden": False}],
            cell_order=["c1"],
            published_by_id=teacher.id,
        )
        db.add(version)
        db.flush()
        tpl.current_version_id = version.id
        db.flush()
        print(f"  [创建] 模板版本 id={version.id}")

    module = db.query(ExperimentModule).filter_by(name="E2E 测试实验").first()
    if not module:
        module = ExperimentModule(name="E2E 测试实验", description="Playwright E2E",
                                  template_id=tpl.id, owner_id=teacher.id,
                                  status="published")
        db.add(module)
        db.flush()
        print(f"  [创建] 模块 id={module.id}")

    # ── 8. 学生实验记录（同一学生+模块已存在则跳过） ──
    print("8. 学生实验记录")
    record = db.query(ExperimentRecord).filter_by(
        module_id=module.id, student_id=student.id,
    ).first()
    if not record:
        version_id = tpl.current_version_id
        record = ExperimentRecord(
            module_id=module.id,
            template_version_id=version_id,
            student_id=student.id,
            status="started",
            started_at=now,
            cells_sources={"c1": "print('hello e2e')"},
        )
        db.add(record)
        db.flush()
        print(f"  [创建] 实验记录 id={record.id}")
    else:
        print("  [跳过] 实验记录")

    db.commit()
    print("\n[创建] 种子数据就绪！")

except Exception as e:
    db.rollback()
    print(f"失败: {e}")
    raise
finally:
    db.close()

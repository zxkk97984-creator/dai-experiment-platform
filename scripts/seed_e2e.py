"""E2E 种子数据——直接通过模型插入，绕过 API 认证"""
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

try:
    # ── 1. 用户 ──
    print("1. 创建用户")
    admin = User(username="admin", real_name="管理员", role="admin",
                 status="active", password_hash=hash_password("Passw0rd!"))
    teacher = User(username="teacher", real_name="测试教师", role="teacher",
                   status="active", password_hash=hash_password("Passw0rd!"))
    student = User(username="student", real_name="测试学生", role="student",
                   status="active", password_hash=hash_password("Passw0rd!"))
    db.add_all([admin, teacher, student])
    db.flush()
    print(f"   admin={admin.id}, teacher={teacher.id}, student={student.id}")

    # ── 2. 课程 ──
    print("2. 创建课程")
    course = Course(title="E2E 测试课程", description="Playwright E2E", status="published",
                    teacher_id=teacher.id)
    db.add(course)
    db.flush()
    cid = course.id
    print(f"   课程 id={cid}")

    # ── 3. 选课 ──
    print("3. 学生选课")
    enroll = CourseEnrollment(course_id=cid, student_id=student.id, status="enrolled")
    db.add(enroll)
    db.flush()

    # ── 4. 章节 + 课时 ──
    print("4. 章节和课时")
    chapter = Chapter(course_id=cid, title="第一章", order_index=1)
    db.add(chapter)
    db.flush()
    lesson = Lesson(chapter_id=chapter.id, title="第一课", content_type="markdown",
                    content="# 测试课时", order_index=1)
    db.add(lesson)
    db.flush()
    print(f"   章节={chapter.id}, 课时={lesson.id}")

    # ── 5. 作业 + 判题题目 ──
    print("5. 作业和判题题目")
    assignment = Assignment(course_id=cid, title="E2E 测试作业", status="published")
    db.add(assignment)
    db.flush()
    question = JudgeQuestion(
        assignment_id=assignment.id,
        title="加法函数", function_name="add",
        public_cases=[{"args": [1, 2], "expected": 3}],
        hidden_tests="import user_code\n\ndef test_hidden():\n    assert user_code.add(1, 2) == 3\n",
        time_limit_ms=10000, memory_limit_mb=256,
    )
    db.add(question)
    db.flush()
    print(f"   作业={assignment.id}, 题目={question.id}")

    # ── 6. 考试 ──
    print("6. 考试")
    exam = Exam(course_id=cid, title="E2E 测试考试", status="published",
                duration_minutes=60)
    db.add(exam)
    db.flush()
    eq = ExamQuestion(
        exam_id=exam.id, question_type="single_choice",
        prompt="1+1=?",
        options={"A": "1", "B": "2", "C": "3", "D": "4"},
        correct_answer={"correct": ["B"]},
        points=10, order_index=1,
    )
    db.add(eq)
    db.flush()
    print(f"   考试={exam.id}, 题目={eq.id}")

    # ── 7. Notebook Template + 实验模块 ──
    print("7. Notebook Template 和实验模块")
    tpl = NotebookTemplate(name="E2E 测试模板", description="E2E",
                           status="published", owner_id=teacher.id,
                           draft_cells=[], draft_revision=1)
    db.add(tpl)
    db.flush()

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

    module = ExperimentModule(name="E2E 测试实验", description="Playwright E2E",
                              template_id=tpl.id, owner_id=teacher.id,
                              status="published")
    db.add(module)
    db.flush()
    print(f"   模板={tpl.id} v{version.id}, 模块={module.id}")

    # ── 8. 学生实验记录 ──
    print("8. 学生实验记录")
    record = ExperimentRecord(
        module_id=module.id,
        template_version_id=version.id,
        student_id=student.id,
        status="started",
        started_at=now,
        cells_sources={"c1": "print('hello e2e')"},
    )
    db.add(record)
    db.flush()
    print(f"   实验记录={record.id}")

    db.commit()
    print("\n✅ 种子数据创建完成！")

except Exception as e:
    db.rollback()
    print(f"❌ 失败: {e}")
    raise
finally:
    db.close()

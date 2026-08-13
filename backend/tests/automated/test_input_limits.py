"""分层输入上限测试（TASK-004 / F-10）。

覆盖：判题提交代码 50k 字符 / 64 KiB、判题题目隐藏测试与代码模板、考试文本答案
单项 20k 字符 / 64 KiB、单题保存端点强类型校验、批量保存整体 422；
超限请求在写库/入队前被拒绝（422），且数据库无副作用。
"""
from datetime import timedelta

import pytest
from conftest import auth_header, create_user, login
from pydantic import ValidationError
from sqlalchemy import func, select

from app.models import (
    Assignment,
    Course,
    CourseEnrollment,
    Exam,
    ExamAnswer,
    ExamQuestion,
    ExamSubmission,
    JudgeQuestion,
    Submission,
)
from app.schemas import ExamAnswerSaveItem, JudgeQuestionCreate, SubmissionCreate
from app.services.time_utils import utc_now

API = "/api/v1"

CODE_MAX = 50_000
TEXT_MAX = 20_000
BYTES_MAX = 64 * 1024


def _token(client, db_session_factory, username, role):
    create_user(db_session_factory, username, role)
    token, _ = login(client, username)
    return token


def _course_for_teacher(db_session_factory, teacher_id):
    with db_session_factory() as db:
        course = Course(
            title="输入上限课程", description="desc", status="published",
            visibility="class", default_score=100, teacher_id=teacher_id,
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        return course.id


def _enroll(db_session_factory, course_id, student_id):
    with db_session_factory() as db:
        db.add(CourseEnrollment(course_id=course_id, student_id=student_id, status="enrolled"))
        db.commit()


def _assignment_question(db_session_factory, course_id):
    with db_session_factory() as db:
        assignment = Assignment(course_id=course_id, title="作业", status="published")
        db.add(assignment)
        db.flush()
        question = JudgeQuestion(
            assignment_id=assignment.id, title="题", function_name="solve",
            hidden_tests="def test_ok():\n    assert True",
            public_cases=[{"args": [], "expected": True}], grading_mode="legacy",
        )
        db.add(question)
        db.commit()
        return assignment.id, question.id


def _exam_with_blank_question(db_session_factory, course_id, student_id):
    with db_session_factory() as db:
        now = utc_now()
        exam = Exam(
            course_id=course_id, title="考试", status="published",
            duration_minutes=60, start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=1),
        )
        db.add(exam)
        db.flush()
        question = ExamQuestion(
            exam_id=exam.id, question_type="fill_blank", prompt="填空 [[blank:a]]",
            correct_answer={"blanks": [{"id": "a", "accepted_answers": ["答案"]}]},
            points=5, order_index=1,
        )
        db.add(question)
        db.flush()
        submission = ExamSubmission(
            exam_id=exam.id, student_id=student_id, status="started",
            started_at=now, expires_at=now + timedelta(minutes=30),
        )
        db.add(submission)
        db.commit()
        return exam.id, question.id


def _submission_count(db_session_factory, question_id=None):
    with db_session_factory() as db:
        query = select(func.count()).select_from(Submission)
        if question_id is not None:
            query = query.where(Submission.question_id == question_id)
        return db.scalar(query) or 0


def _answer_count(db_session_factory, exam_id):
    with db_session_factory() as db:
        return db.scalar(
            select(func.count()).select_from(ExamAnswer).join(
                ExamSubmission, ExamAnswer.submission_id == ExamSubmission.id
            ).where(ExamSubmission.exam_id == exam_id)
        ) or 0


# ═══════════════════════════════════════════════════════════════
# Schema 单元校验：字符与 UTF-8 字节双边界
# ═══════════════════════════════════════════════════════════════


def test_submission_code_char_boundary():
    SubmissionCreate(question_id=1, code="x" * CODE_MAX)  # 边界值合法
    with pytest.raises(ValidationError):
        SubmissionCreate(question_id=1, code="x" * (CODE_MAX + 1))


def test_submission_code_multibyte_byte_boundary():
    # 20,000 个汉字 = 60,000 字节 ≤ 64 KiB，字符数也 ≤ 50k → 合法
    SubmissionCreate(question_id=1, code="汉" * 20_000)
    # 22,000 个汉字 = 66,000 字节 > 64 KiB（字符数 22k < 50k，只能靠字节上限拦截）→ 拒绝
    with pytest.raises(ValidationError):
        SubmissionCreate(question_id=1, code="汉" * 22_000)


def test_judge_question_hidden_tests_boundary():
    JudgeQuestionCreate(
        title="t", function_name="f",
        hidden_tests="x" * CODE_MAX,
    )
    with pytest.raises(ValidationError):
        JudgeQuestionCreate(
            title="t", function_name="f",
            hidden_tests="x" * (CODE_MAX + 1),
        )
    with pytest.raises(ValidationError):
        JudgeQuestionCreate(title="t", function_name="f", hidden_tests="汉" * 22_000)


def test_exam_text_answer_char_boundary():
    ExamAnswerSaveItem(question_id=1, text_answers={"a": "x" * TEXT_MAX})
    with pytest.raises(ValidationError):
        ExamAnswerSaveItem(question_id=1, text_answers={"a": "x" * (TEXT_MAX + 1)})


def test_exam_text_answer_multibyte_byte_boundary():
    ExamAnswerSaveItem(question_id=1, text_answers={"a": "汉" * 20_000})
    with pytest.raises(ValidationError):
        ExamAnswerSaveItem(question_id=1, text_answers={"a": "汉" * 22_000})


# ═══════════════════════════════════════════════════════════════
# API 层：提交代码上限 + 无副作用
# ═══════════════════════════════════════════════════════════════


@pytest.fixture()
def judge_context(client, db_session_factory):
    teacher_id = create_user(db_session_factory, "il-teacher", "teacher").id
    student_id = create_user(db_session_factory, "il-student", "student").id
    student_token, _ = login(client, "il-student")
    course_id = _course_for_teacher(db_session_factory, teacher_id)
    _enroll(db_session_factory, course_id, student_id)
    _, question_id = _assignment_question(db_session_factory, course_id)
    return student_token, question_id


def test_submit_oversized_code_rejected_without_side_effect(client, db_session_factory, judge_context):
    student_token, question_id = judge_context
    before = _submission_count(db_session_factory, question_id)
    response = client.post(
        f"{API}/judge/submissions", headers=auth_header(student_token),
        json={"question_id": question_id, "code": "x" * (CODE_MAX + 1)},
    )
    assert response.status_code == 422, response.text
    assert _submission_count(db_session_factory, question_id) == before


def test_submit_boundary_code_accepted(client, db_session_factory, judge_context):
    student_token, question_id = judge_context
    response = client.post(
        f"{API}/judge/submissions", headers=auth_header(student_token),
        json={"question_id": question_id, "code": "x" * CODE_MAX},
    )
    assert response.status_code == 201, response.text
    assert _submission_count(db_session_factory, question_id) == 1


def test_submit_multibyte_oversized_code_rejected(client, db_session_factory, judge_context):
    student_token, question_id = judge_context
    before = _submission_count(db_session_factory, question_id)
    response = client.post(
        f"{API}/judge/submissions", headers=auth_header(student_token),
        json={"question_id": question_id, "code": "汉" * 22_000},
    )
    assert response.status_code == 422, response.text
    assert _submission_count(db_session_factory, question_id) == before


# ═══════════════════════════════════════════════════════════════
# API 层：考试答案单题保存（put_answer 强类型化）
# ═══════════════════════════════════════════════════════════════


@pytest.fixture()
def exam_context(client, db_session_factory):
    teacher = create_user(db_session_factory, "il-exam-teacher", "teacher")
    student_id = create_user(db_session_factory, "il-exam-student", "student").id
    student_token, _ = login(client, "il-exam-student")
    course_id = _course_for_teacher(db_session_factory, teacher.id)
    _enroll(db_session_factory, course_id, student_id)
    exam_id, question_id = _exam_with_blank_question(db_session_factory, course_id, student_id)
    return student_token, exam_id, question_id


def test_put_answer_oversized_text_rejected(client, db_session_factory, exam_context):
    student_token, exam_id, question_id = exam_context
    before = _answer_count(db_session_factory, exam_id)
    response = client.put(
        f"{API}/exams/{exam_id}/answers/{question_id}", headers=auth_header(student_token),
        json={"text_answers": {"a": "x" * (TEXT_MAX + 1)}},
    )
    assert response.status_code == 422, response.text
    assert _answer_count(db_session_factory, exam_id) == before


def test_put_answer_multibyte_oversized_rejected(client, db_session_factory, exam_context):
    student_token, exam_id, question_id = exam_context
    before = _answer_count(db_session_factory, exam_id)
    response = client.put(
        f"{API}/exams/{exam_id}/answers/{question_id}", headers=auth_header(student_token),
        json={"text_answers": {"a": "汉" * 22_000}},
    )
    assert response.status_code == 422, response.text
    assert _answer_count(db_session_factory, exam_id) == before


def test_put_answer_boundary_text_accepted(client, db_session_factory, exam_context):
    student_token, exam_id, question_id = exam_context
    response = client.put(
        f"{API}/exams/{exam_id}/answers/{question_id}", headers=auth_header(student_token),
        json={"text_answers": {"a": "x" * TEXT_MAX}, "expected_version": 0},
    )
    assert response.status_code == 201, response.text
    assert _answer_count(db_session_factory, exam_id) == 1


# ═══════════════════════════════════════════════════════════════
# API 层：批量保存——整包 422 且无副作用
# ═══════════════════════════════════════════════════════════════


def test_batch_save_oversized_item_rejects_whole_request(client, db_session_factory, exam_context):
    student_token, exam_id, question_id = exam_context
    before = _answer_count(db_session_factory, exam_id)
    response = client.put(
        f"{API}/exams/{exam_id}/answers", headers=auth_header(student_token),
        json={"answers": [{"question_id": question_id, "text_answers": {"a": "x" * (TEXT_MAX + 1)}}]},
    )
    assert response.status_code == 422, response.text
    assert _answer_count(db_session_factory, exam_id) == before


def test_batch_save_boundary_accepted(client, db_session_factory, exam_context):
    student_token, exam_id, question_id = exam_context
    response = client.put(
        f"{API}/exams/{exam_id}/answers", headers=auth_header(student_token),
        json={"answers": [{"question_id": question_id, "text_answers": {"a": "x" * TEXT_MAX}}]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["ok"] is True
    assert _answer_count(db_session_factory, exam_id) == 1

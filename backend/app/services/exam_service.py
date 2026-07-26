"""考试系统业务逻辑"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.errors import api_error
from app.models import Exam, ExamAnswer, ExamGrade, ExamQuestion, ExamSubmission, User

def require_exam_editable(exam, user):
    if user.role != "admin" and exam.created_by_id != user.id:
        raise api_error(403, "FORBIDDEN", "只能管理自己的考试")
    if exam.status != "draft":
        raise api_error(403, "EXAM_LOCKED", "考试已发布，不能修改题目")

def validate_publish(exam, db):
    if exam.start_at and exam.end_at and exam.start_at >= exam.end_at:
        raise api_error(422, "PUBLISH_INVALID", "开始时间必须早于结束时间")
    if not exam.duration_minutes or exam.duration_minutes <= 0:
        raise api_error(422, "PUBLISH_INVALID", "考试时长必须大于0")
    questions = db.scalars(select(ExamQuestion).where(ExamQuestion.exam_id == exam.id)).all()
    if not questions:
        raise api_error(422, "PUBLISH_INVALID", "至少需要一道题目")
    total = sum(q.points for q in questions)
    if total <= 0:
        raise api_error(422, "PUBLISH_INVALID", "总分必须大于0")
def start_exam(exam, student, db):
    now = datetime.now(timezone.utc)
    def _tz(dt): return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt
    existing = db.scalar(select(ExamSubmission).where(
        ExamSubmission.exam_id == exam.id, ExamSubmission.student_id == student.id))
    if existing:
        if existing.status == "started":
            if existing.expires_at and _tz(existing.expires_at) < now:
                _auto_submit(existing, db, now)
                raise api_error(403, "EXAM_EXPIRED", "考试已过期")
            return existing
        raise api_error(403, "EXAM_ALREADY_SUBMITTED", "考试已提交")
    expires_at = now + timedelta(minutes=exam.duration_minutes)
    if exam.end_at and expires_at > exam.end_at.replace(tzinfo=timezone.utc):
        expires_at = exam.end_at.replace(tzinfo=timezone.utc)
    sub = ExamSubmission(exam_id=exam.id, student_id=student.id, status="started",
                         started_at=now, expires_at=expires_at)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def save_answer(db, exam_id, question_id, student, payload):
    sub = db.scalar(select(ExamSubmission).where(
        ExamSubmission.exam_id == exam_id, ExamSubmission.student_id == student.id))
    if not sub or sub.status != "started":
        raise api_error(403, "EXAM_NOT_STARTED", "考试未开始或已结束")
    now = datetime.now(timezone.utc)
    if sub.expires_at and sub.expires_at.replace(tzinfo=timezone.utc) < now:
        _auto_submit(sub, db, now)
        raise api_error(403, "EXAM_EXPIRED", "考试已过期")
    q = db.get(ExamQuestion, question_id)
    if not q or q.exam_id != exam_id:
        raise api_error(404, "QUESTION_NOT_FOUND", "题目不存在")
    ans = db.scalar(select(ExamAnswer).where(
        ExamAnswer.submission_id == sub.id, ExamAnswer.question_id == question_id))
    if not ans:
        ans = ExamAnswer(submission_id=sub.id, question_id=question_id)
        db.add(ans)
    if q.question_type == "code":
        ans.code_answer = payload.get("code_answer", "")
    else:
        ans.selected_options = payload.get("selected_options", [])
    db.commit()
    db.refresh(ans)
    return ans


def submit_exam(exam, student, db):
    """交卷：先 DB 持久化答案 → 再入队 Redis → 最后汇总成绩。

    幂等：已 submitted/grading/graded 的提交直接返回。
    """
    now = datetime.now(timezone.utc)
    sub = db.scalar(select(ExamSubmission).where(
        ExamSubmission.exam_id == exam.id, ExamSubmission.student_id == student.id))
    if not sub:
        sub = ExamSubmission(exam_id=exam.id, student_id=student.id, status="started",
                             started_at=now, expires_at=now + timedelta(minutes=exam.duration_minutes))
        db.add(sub)
        db.flush()
    if sub.status in ("submitted", "grading", "graded"):
        return sub

    sub.status = "grading"
    sub.submitted_at = now
    db.commit()

    questions = db.scalars(select(ExamQuestion).where(ExamQuestion.exam_id == exam.id)).all()
    answers = db.scalars(select(ExamAnswer).where(ExamAnswer.submission_id == sub.id)).all()
    by_qid = {a.question_id: a for a in answers}

    code_answers_to_enqueue = []  # (ans, q)
    total = 0.0
    all_done = True

    for q in questions:
        ans = by_qid.get(q.id)
        if not ans:
            continue
        if q.question_type == "single_choice":
            correct = q.correct_answer.get("correct", [])
            score = q.points if (ans.selected_options or []) == correct else 0
            ans.score = score
            ans.grading_status = "completed"
            total += score
        elif q.question_type == "multi_choice":
            correct = set(q.correct_answer.get("correct", []))
            selected = set(ans.selected_options or [])
            score = q.points if correct == selected else 0
            ans.score = score
            ans.grading_status = "completed"
            total += score
        elif q.question_type == "code":
            if ans.code_answer and q.hidden_tests:
                ans.grading_status = "pending"
                code_answers_to_enqueue.append((ans, q))
                all_done = False
            else:
                ans.score = 0
                ans.grading_status = "completed"

    # 先持久化所有答案状态到数据库
    db.commit()

    # 数据库提交成功后再入队 Redis；入队失败则回写 system_error
    for ans, q in code_answers_to_enqueue:
        try:
            from app.worker.judge_worker import enqueue_exam_answer
            enqueue_exam_answer(sub.id, ans.id, q)
        except Exception:
            ans.grading_status = "completed"
            ans.system_error = "判题队列不可用"
            ans.score = 0
            db.commit()

    # 重新检查是否所有答案都已完成（入队失败的已被标记为 completed）
    remaining_pending = db.scalar(
        select(ExamAnswer).where(
            ExamAnswer.submission_id == sub.id,
            ExamAnswer.grading_status == "pending",
        ).limit(1)
    )
    if not remaining_pending:
        total = db.scalar(
            select(func.sum(ExamAnswer.score)).where(
                ExamAnswer.submission_id == sub.id,
                ExamAnswer.grading_status == "completed",
            )
        ) or 0.0
        _finalize_grade(sub, float(total), db)
        db.commit()

    db.refresh(sub)
    return sub


def _auto_submit(sub, db, now):
    """自动交卷：先评分选择题 → 提交 DB → 代码题入队 → 汇总"""
    sub.status = "grading"
    sub.submitted_at = now
    questions = db.scalars(select(ExamQuestion).where(ExamQuestion.exam_id == sub.exam_id)).all()
    answers = db.scalars(select(ExamAnswer).where(ExamAnswer.submission_id == sub.id)).all()
    by_qid = {a.question_id: a for a in answers}
    total = 0.0
    code_answers_to_enqueue = []

    for q in questions:
        ans = by_qid.get(q.id)
        if not ans:
            continue
        if q.question_type in ("single_choice", "multi_choice"):
            correct = set(q.correct_answer.get("correct", []))
            selected = set(ans.selected_options or [])
            ans.score = q.points if correct == selected else 0
            ans.grading_status = "completed"
            total += ans.score
        elif q.question_type == "code":
            if ans.code_answer and q.hidden_tests:
                ans.grading_status = "pending"
                code_answers_to_enqueue.append((ans, q))
            else:
                ans.score = 0
                ans.grading_status = "completed"

    # 先持久化
    db.commit()

    # 入队代码题
    for ans, q in code_answers_to_enqueue:
        try:
            from app.worker.judge_worker import enqueue_exam_answer
            enqueue_exam_answer(sub.id, ans.id, q)
        except Exception:
            ans.grading_status = "completed"
            ans.system_error = "判题队列不可用"
            ans.score = 0
            db.commit()

    # 检查是否全部完成
    remaining_pending = db.scalar(
        select(ExamAnswer).where(
            ExamAnswer.submission_id == sub.id,
            ExamAnswer.grading_status == "pending",
        ).limit(1)
    )
    if not remaining_pending:
        total = db.scalar(
            select(func.sum(ExamAnswer.score)).where(
                ExamAnswer.submission_id == sub.id,
                ExamAnswer.grading_status == "completed",
            )
        ) or 0.0
        _finalize_grade(sub, float(total), db)
        db.commit()


def _finalize_grade(sub, score, db):
    sub.score = float(score)
    sub.status = "graded"
    sub.graded_at = datetime.now(timezone.utc)
    grade = db.scalar(select(ExamGrade).where(
        ExamGrade.exam_id == sub.exam_id, ExamGrade.student_id == sub.student_id))
    if grade:
        grade.score = float(score)
    else:
        db.add(ExamGrade(exam_id=sub.exam_id, student_id=sub.student_id, score=float(score)))


def get_my_grade(exam_id, student, db):
    sub = db.scalar(select(ExamSubmission).where(
        ExamSubmission.exam_id == exam_id, ExamSubmission.student_id == student.id))
    if not sub:
        raise api_error(404, "SUBMISSION_NOT_FOUND", "未找到考试记录")
    answers = db.scalars(select(ExamAnswer).where(ExamAnswer.submission_id == sub.id)).all()
    return {"submission_id": sub.id, "status": sub.status, "score": sub.score,
            "started_at": sub.started_at.isoformat() if sub.started_at else None,
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
            "answers": [{"question_id": a.question_id, "grading_status": a.grading_status,
                         "score": a.score, "system_error": a.system_error} for a in answers]}


def scan_expired_exams(db, now):
    expired = db.scalars(select(ExamSubmission).where(
        ExamSubmission.status == "started", ExamSubmission.expires_at < now)).all()
    for sub in expired:
        _auto_submit(sub, db, now)
    return len(expired)
def create_question(db, exam_id, payload, user):
    exam = db.get(Exam, exam_id)
    if not exam:
        raise api_error(404, "EXAM_NOT_FOUND", "考试不存在")
    require_exam_editable(exam, user)
    q = ExamQuestion(exam_id=exam_id, **payload)
    db.add(q)
    db.commit()
    db.refresh(q)
    return q

def list_questions(db, exam_id):
    return list(db.scalars(select(ExamQuestion).where(ExamQuestion.exam_id == exam_id).order_by(ExamQuestion.order_index)))

def get_question(db, exam_id, question_id):
    q = db.get(ExamQuestion, question_id)
    if not q or q.exam_id != exam_id:
        raise api_error(404, "QUESTION_NOT_FOUND", "题目不存在")
    return q

def update_question(db, exam_id, question_id, payload, user):
    exam = db.get(Exam, exam_id)
    require_exam_editable(exam, user)
    q = get_question(db, exam_id, question_id)
    for key, value in payload.items():
        setattr(q, key, value)
    db.commit()
    db.refresh(q)
    return q

def delete_question(db, exam_id, question_id, user):
    exam = db.get(Exam, exam_id)
    require_exam_editable(exam, user)
    q = get_question(db, exam_id, question_id)
    db.delete(q)
    db.commit()

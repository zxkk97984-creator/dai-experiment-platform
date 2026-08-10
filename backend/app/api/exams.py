from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.courses import can_access_course_content, ensure_course_manager, require_course
from app.config import Settings, get_settings
from app.dependencies import get_current_user, get_db, require_roles
from app.errors import api_error
from app.models import Course, CourseEnrollment, Exam, ExamAnswer, ExamGrade, ExamQuestion, ExamSubmission, QuestionRubric, User
from app.schemas import ExamCreate, ExamGradeRead, ExamQuestionCreate, ExamQuestionRead, ExamQuestionTeacherRead, ExamQuestionUpdate, ExamRead, ExamRetryRequest, ExamSubmitRequest, ExamSubmissionRead, ExamUpdate, PaginatedResponse
from app.services.exam_service import create_question, delete_question, get_my_grade, get_question, list_questions, require_exam_editable, retry_exam_submission as retry_exam_submission_service, save_answer, start_exam as svc_start_exam, submit_exam as svc_submit_exam, update_question, validate_publish

router = APIRouter(prefix="/exams", tags=["exams"])


def require_exam(exam_id: int, db: Session) -> Exam:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise api_error(404, "EXAM_NOT_FOUND", "考试不存在")
    return exam


def _submitted_ids(db: Session, exams: list[Exam], student_id: int) -> set[int]:
    """批量计算学生已提交的考试 id 集合，避免逐考试 N+1 查询。

    语义与 dashboard 待办判定一致：存在 submitted/grading/graded 任一状态的
    提交记录即视为已考。
    """
    if not exams:
        return set()
    exam_ids = [e.id for e in exams]
    return set(
        db.scalars(
            select(ExamSubmission.exam_id).where(
                ExamSubmission.exam_id.in_(exam_ids),
                ExamSubmission.student_id == student_id,
                ExamSubmission.status.in_(("submitted", "grading", "graded")),
            )
        ).all()
    )


@router.get("", response_model=PaginatedResponse)
def list_exams(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Exam)
    count_query = select(func.count()).select_from(Exam)
    if current_user.role == "student":
        query = (
            query.join(Course, Exam.course_id == Course.id)
            .join(CourseEnrollment, Course.id == CourseEnrollment.course_id)
            .where(Exam.status == "published")
            .where(Course.status == "published")
            .where(CourseEnrollment.student_id == current_user.id)
            .where(CourseEnrollment.status == "enrolled")
        )
        count_query = (
            count_query.join(Course, Exam.course_id == Course.id)
            .join(CourseEnrollment, Course.id == CourseEnrollment.course_id)
            .where(Exam.status == "published")
            .where(Course.status == "published")
            .where(CourseEnrollment.student_id == current_user.id)
            .where(CourseEnrollment.status == "enrolled")
        )
    elif current_user.role == "teacher":
        query = query.join(Course, Exam.course_id == Course.id).where(Course.teacher_id == current_user.id)
        count_query = count_query.join(Course, Exam.course_id == Course.id).where(Course.teacher_id == current_user.id)
    elif current_user.role != "admin":
        # developer or any unsupported role: empty
        query = query.where(Exam.id == -1)
        count_query = count_query.where(Exam.id == -1)
    total = db.scalar(count_query) or 0
    exams = db.scalars(query.order_by(Exam.id).offset((page - 1) * page_size).limit(page_size)).all()
    # 仅学生视角计算已交状态，供任务中心区分已交/待办（教师/管理员保持默认 False）
    submitted_ids = _submitted_ids(db, exams, current_user.id) if current_user.role == "student" else set()
    items = []
    for exam in exams:
        data = ExamRead.model_validate(exam).model_dump()
        if current_user.role == "student":
            data["is_submitted"] = exam.id in submitted_ids
        else:
            data.update({
                "course_title": exam.course.title if exam.course else "",
                "question_count": db.scalar(
                    select(func.count()).select_from(ExamQuestion).where(ExamQuestion.exam_id == exam.id)
                ) or 0,
                "participant_count": db.scalar(
                    select(func.count()).select_from(ExamSubmission).where(
                        ExamSubmission.exam_id == exam.id,
                        ExamSubmission.status.in_(("submitted", "grading", "graded", "review_required")),
                    )
                ) or 0,
                "expected_count": db.scalar(
                    select(func.count()).select_from(CourseEnrollment).where(
                        CourseEnrollment.course_id == exam.course_id,
                        CourseEnrollment.status == "enrolled",
                    )
                ) or 0,
                "created_at": exam.created_at,
                "updated_at": exam.updated_at,
            })
        items.append(data)
    return PaginatedResponse(items=items, page=page, page_size=page_size, total=total)


@router.post("", response_model=ExamRead, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    course = require_course(payload.course_id, db)
    if current_user.role == "teacher":
        if course.teacher_id != current_user.id:
            raise api_error(403, "FORBIDDEN", "只能在自己的课程中创建考试")
    # 创建考试时强制 draft，发布需通过 update 接口触发 validate_publish()
    exam_data = payload.model_dump()
    exam_data["status"] = "draft"
    exam = Exam(**exam_data, created_by_id=current_user.id)
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@router.get("/{exam_id}", response_model=ExamRead)
def get_exam(exam_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    exam = require_exam(exam_id, db)
    if not can_access_course_content(exam.course, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限查看该考试")
    if current_user.role == "student" and exam.status != "published":
        raise api_error(403, "EXAM_NOT_AVAILABLE", "考试未发布")
    return exam


@router.patch("/{exam_id}", response_model=ExamRead)
def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    exam = require_exam(exam_id, db)
    ensure_course_manager(exam.course, current_user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(exam, key, value)
    # 发布时强制校验
    if exam.status == "published":
        validate_publish(exam, db)
        # AI 评分门禁：非 legacy 编程题必须由教师检查并锁定 Rubric。
        code_questions = db.scalars(
            select(ExamQuestion).where(
                ExamQuestion.exam_id == exam_id,
                ExamQuestion.question_type == "code",
                ExamQuestion.grading_mode != "legacy",
            )
        ).all()
        if code_questions:
            if not settings.ai_ready:
                raise api_error(503, "AI_NOT_READY", "发布含 AI 评分的考试需要配置 DAI_AI_API_KEY")
            missing = []
            for question in code_questions:
                locked = db.scalar(select(QuestionRubric.id).where(
                    QuestionRubric.exam_question_id == question.id,
                    QuestionRubric.status == "locked",
                ).limit(1))
                if locked is None:
                    missing.append(str(question.order_index + 1))
            if missing:
                raise api_error(422, "AI_RUBRIC_REQUIRED", "以下编程题尚未锁定 Rubric：第 " + "、".join(missing) + " 题")
    db.commit()
    db.refresh(exam)
    return exam


@router.post("/{exam_id}/start", response_model=ExamSubmissionRead, status_code=status.HTTP_201_CREATED)
def start_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    exam = require_exam(exam_id, db)
    course = db.get(Course, exam.course_id)
    if not course or not can_access_course_content(course, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限参加该考试")
    if exam.status != "published":
        raise api_error(403, "EXAM_NOT_AVAILABLE", "考试未发布")

    # 检查时间窗口（统一使用 as_utc 规范化）
    from app.services.time_utils import as_utc, utc_now
    now = utc_now()
    if exam.start_at is not None and as_utc(exam.start_at) > now:
        raise api_error(403, "EXAM_NOT_STARTED", "考试尚未开始")
    if exam.end_at is not None and as_utc(exam.end_at) <= now:
        raise api_error(403, "EXAM_EXPIRED", "考试已结束")

    return svc_start_exam(exam, current_user, db)


@router.post("/{exam_id}/submit", response_model=ExamSubmissionRead, status_code=status.HTTP_201_CREATED)
def submit_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    exam = require_exam(exam_id, db)
    course = db.get(Course, exam.course_id)
    if not course or not can_access_course_content(course, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限提交该考试")
    if exam.status != "published":
        raise api_error(403, "EXAM_NOT_AVAILABLE", "考试未发布")
    # 必须有提交记录（至少 started），已 grading/graded/submitted 由 service 层幂等处理
    sub = db.scalar(
        select(ExamSubmission).where(
            ExamSubmission.exam_id == exam_id,
            ExamSubmission.student_id == current_user.id,
        )
    )
    if not sub:
        raise api_error(403, "EXAM_NOT_STARTED", "请先开始考试")
    # 幂等：重复提交返回当前状态，不报错（review_required 不自动重试）
    if sub.status in ("submitted", "grading", "graded", "review_required"):
        return ExamSubmissionRead.model_validate(sub)
    return svc_submit_exam(exam, current_user, db)


@router.post("/{exam_id}/submissions/{submission_id}/retry", response_model=ExamSubmissionRead)
def retry_exam_submission(
    exam_id: int,
    submission_id: int,
    payload: ExamRetryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    """显式重试 review_required 的考试提交（教师/管理员受控入口）"""
    exam = require_exam(exam_id, db)
    ensure_course_manager(exam.course, current_user)
    sub = db.get(ExamSubmission, submission_id)
    if not sub or sub.exam_id != exam_id:
        raise api_error(404, "SUBMISSION_NOT_FOUND", "考试提交不存在")
    return retry_exam_submission_service(submission_id, payload.answer_ids, current_user, db)


@router.get("/{exam_id}/grades")
def exam_grades(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    exam = require_exam(exam_id, db)
    if current_user.role == "teacher":
        ensure_course_manager(exam.course, current_user)
    submissions = db.scalars(
        select(ExamSubmission).where(ExamSubmission.exam_id == exam_id).order_by(ExamSubmission.id)
    ).all()
    submission_by_student = {submission.student_id: submission for submission in submissions}

    enrolled_students = db.scalars(
        select(User)
        .join(CourseEnrollment, CourseEnrollment.student_id == User.id)
        .where(
            CourseEnrollment.course_id == exam.course_id,
            CourseEnrollment.status == "enrolled",
        )
        .order_by(User.id)
    ).all()
    students_by_id = {student.id: student for student in enrolled_students}
    for submission in submissions:
        students_by_id.setdefault(submission.student_id, submission.student)

    items = []
    for student in students_by_id.values():
        submission = submission_by_student.get(student.id)
        score = submission.score if submission else None
        items.append({
            "id": submission.id if submission else f"absent-{student.id}",
            "exam_id": exam.id,
            "student_id": student.id,
            "student_name": student.real_name,
            "student_number": student.username,
            "submission_id": submission.id if submission else None,
            "status": submission.status if submission else "absent",
            "score": score,
            "started_at": submission.started_at if submission else None,
            "submitted_at": submission.submitted_at if submission else None,
            "graded_at": submission.graded_at if submission else None,
            "review_reason": submission.review_reason if submission else None,
        })

    scored = [float(item["score"]) for item in items if item["score"] is not None]
    submitted_count = sum(1 for item in items if item["status"] in ("submitted", "grading", "graded", "review_required"))
    pass_count = sum(1 for score in scored if score >= 60)
    distribution = []
    for label, low, high in (("90–100", 90, 101), ("80–89", 80, 90), ("70–79", 70, 80), ("60–69", 60, 70), ("0–59", 0, 60)):
        distribution.append({"label": label, "count": sum(1 for score in scored if low <= score < high)})

    question_count = db.scalar(
        select(func.count()).select_from(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
    ) or 0
    total_score = db.scalar(
        select(func.sum(ExamQuestion.points)).where(ExamQuestion.exam_id == exam_id)
    ) or 0
    return {
        "items": items,
        "page": 1,
        "page_size": len(items) or 20,
        "total": len(items),
        "exam": {
            "id": exam.id,
            "title": exam.title,
            "status": exam.status,
            "course_id": exam.course_id,
            "course_title": exam.course.title if exam.course else "",
            "duration_minutes": exam.duration_minutes,
            "question_count": question_count,
            "total_score": float(total_score),
        },
        "summary": {
            "expected_count": len(items),
            "submitted_count": submitted_count,
            "graded_count": len(scored),
            "average_score": round(sum(scored) / len(scored), 1) if scored else None,
            "highest_score": max(scored) if scored else None,
            "pass_rate": round(pass_count * 100 / len(scored), 1) if scored else 0,
            "excellent_rate": round(sum(1 for score in scored if score >= 90) * 100 / len(scored), 1) if scored else 0,
        },
        "distribution": distribution,
    }


@router.get("/{exam_id}/grades/{submission_id}")
def exam_grade_detail(
    exam_id: int,
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    exam = require_exam(exam_id, db)
    if current_user.role == "teacher":
        ensure_course_manager(exam.course, current_user)
    submission = db.get(ExamSubmission, submission_id)
    if not submission or submission.exam_id != exam_id:
        raise api_error(404, "SUBMISSION_NOT_FOUND", "考试提交不存在")

    answers = db.scalars(
        select(ExamAnswer)
        .join(ExamQuestion, ExamQuestion.id == ExamAnswer.question_id)
        .where(ExamAnswer.submission_id == submission_id)
        .order_by(ExamQuestion.order_index, ExamQuestion.id)
    ).all()
    objective_score = sum(float(answer.score or 0) for answer in answers if answer.question.question_type != "code")
    objective_total = sum(float(answer.question.points) for answer in answers if answer.question.question_type != "code")
    code_score = sum(float(answer.score or 0) for answer in answers if answer.question.question_type == "code")
    code_total = sum(float(answer.question.points) for answer in answers if answer.question.question_type == "code")
    elapsed_minutes = None
    if submission.started_at and submission.submitted_at:
        try:
            elapsed_minutes = max(1, round((submission.submitted_at - submission.started_at).total_seconds() / 60))
        except TypeError:
            elapsed_minutes = None

    return {
        "exam": {
            "id": exam.id,
            "title": exam.title,
            "course_title": exam.course.title if exam.course else "",
            "duration_minutes": exam.duration_minutes,
        },
        "student": {
            "id": submission.student.id,
            "name": submission.student.real_name,
            "number": submission.student.username,
        },
        "submission": {
            "id": submission.id,
            "status": submission.status,
            "score": submission.score,
            "started_at": submission.started_at,
            "submitted_at": submission.submitted_at,
            "graded_at": submission.graded_at,
            "elapsed_minutes": elapsed_minutes,
            "review_reason": submission.review_reason,
        },
        "analysis": {
            "objective_score": round(objective_score, 1),
            "objective_total": round(objective_total, 1),
            "code_score": round(code_score, 1),
            "code_total": round(code_total, 1),
            "question_count": len(answers),
            "correct_count": sum(1 for answer in answers if answer.score is not None and float(answer.score) >= float(answer.question.points)),
        },
        "answers": [
            {
                "id": answer.id,
                "question_id": answer.question_id,
                "order_index": answer.question.order_index,
                "question_type": answer.question.question_type,
                "prompt": answer.question.prompt,
                "points": float(answer.question.points),
                "score": float(answer.score) if answer.score is not None else None,
                "grading_status": answer.grading_status,
                "selected_options": answer.selected_options,
                "code_answer": answer.code_answer,
                "system_error": answer.system_error,
            }
            for answer in answers
        ],
    }


# ── 考试题目管理 ──

@router.get("/{exam_id}/questions", response_model=PaginatedResponse)
def get_questions(exam_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    exam = require_exam(exam_id, db)
    if current_user.role == "student":
        # 学生必须已选课且考试已发布
        if exam.status != "published":
            raise api_error(403, "EXAM_NOT_AVAILABLE", "考试未发布")
        if not can_access_course_content(exam.course, current_user, db):
            raise api_error(403, "FORBIDDEN", "请先选课")
        # 学生必须已开始考试
        sub = db.scalar(
            select(ExamSubmission).where(
                ExamSubmission.exam_id == exam_id,
                ExamSubmission.student_id == current_user.id,
            )
        )
        if not sub or sub.status != "started":
            raise api_error(403, "EXAM_NOT_STARTED", "请先开始考试")
    elif current_user.role == "teacher":
        # 教师只能看自己课程的考试题目
        course = db.get(Course, exam.course_id)
        if not course or course.teacher_id != current_user.id:
            raise api_error(403, "FORBIDDEN", "无权查看该考试题目")
    elif current_user.role == "developer":
        # 开发者无权查看考试题目
        raise api_error(403, "FORBIDDEN", "无权查看考试题目")
    # admin 可以查看全部

    questions = list_questions(db, exam_id)
    if current_user.role in ("teacher", "admin"):
        locked_ids = set(db.scalars(select(QuestionRubric.exam_question_id).where(
            QuestionRubric.exam_question_id.in_([q.id for q in questions]),
            QuestionRubric.status == "locked",
        )).all()) if questions else set()
        items = [ExamQuestionTeacherRead.model_validate({
            **{column.name: getattr(q, column.name) for column in q.__table__.columns},
            "has_locked_rubric": q.id in locked_ids,
        }) for q in questions]
    else:
        items = [ExamQuestionRead.model_validate(q) for q in questions]
    return PaginatedResponse(items=items, page=1, page_size=len(items), total=len(items))

@router.post("/{exam_id}/questions", response_model=ExamQuestionRead, status_code=status.HTTP_201_CREATED)
def post_question(exam_id: int, payload: ExamQuestionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return create_question(db, exam_id, payload.model_dump(exclude_unset=True), current_user)

@router.patch("/{exam_id}/questions/{question_id}", response_model=ExamQuestionRead)
def patch_question(exam_id: int, question_id: int, payload: ExamQuestionUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return update_question(db, exam_id, question_id, payload.model_dump(exclude_unset=True), current_user)

@router.delete("/{exam_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def del_question(exam_id: int, question_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    delete_question(db, exam_id, question_id, current_user)
    return None

# ── 学生答题 ──

@router.put("/{exam_id}/answers/{question_id}", status_code=status.HTTP_201_CREATED)
def put_answer(exam_id: int, question_id: int, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(require_roles("student"))):
    return save_answer(db, exam_id, question_id, current_user, payload)

@router.get("/{exam_id}/my-grade")
def my_grade(exam_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles("student"))):
    return get_my_grade(exam_id, current_user, db)

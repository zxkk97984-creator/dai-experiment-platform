from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.courses import can_view_course, ensure_course_manager, require_course
from app.dependencies import get_current_user, get_db, require_roles
from app.errors import api_error
from app.models import Exam, ExamGrade, ExamSubmission, User
from app.schemas import ExamCreate, ExamGradeRead, ExamRead, ExamSubmitRequest, ExamSubmissionRead, ExamUpdate, PaginatedResponse

router = APIRouter(prefix="/exams", tags=["exams"])


def require_exam(exam_id: int, db: Session) -> Exam:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise api_error(404, "EXAM_NOT_FOUND", "考试不存在")
    return exam


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
        query = query.where(Exam.status == "published")
        count_query = count_query.where(Exam.status == "published")
    total = db.scalar(count_query) or 0
    exams = db.scalars(query.order_by(Exam.id).offset((page - 1) * page_size).limit(page_size)).all()
    return PaginatedResponse(items=[ExamRead.model_validate(exam) for exam in exams], page=page, page_size=page_size, total=total)


@router.post("", response_model=ExamRead, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    course = require_course(payload.course_id, db)
    if current_user.role == "teacher":
        if course.teacher_id is None:
            course.teacher_id = current_user.id
        ensure_course_manager(course, current_user)
    exam = Exam(**payload.model_dump(), created_by_id=current_user.id)
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@router.get("/{exam_id}", response_model=ExamRead)
def get_exam(exam_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    exam = require_exam(exam_id, db)
    if not can_view_course(exam.course, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限查看该考试")
    return exam


@router.patch("/{exam_id}", response_model=ExamRead)
def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exam = require_exam(exam_id, db)
    ensure_course_manager(exam.course, current_user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(exam, key, value)
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
    if exam.status != "published":
        raise api_error(400, "EXAM_NOT_AVAILABLE", "考试不可开始")
    submission = db.scalar(select(ExamSubmission).where(ExamSubmission.exam_id == exam_id, ExamSubmission.student_id == current_user.id))
    if not submission:
        submission = ExamSubmission(exam_id=exam_id, student_id=current_user.id, status="started", started_at=datetime.now(UTC))
        db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


@router.post("/{exam_id}/submit", response_model=ExamSubmissionRead, status_code=status.HTTP_201_CREATED)
def submit_exam(
    exam_id: int,
    payload: ExamSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    exam = require_exam(exam_id, db)
    if exam.status != "published":
        raise api_error(400, "EXAM_NOT_AVAILABLE", "考试不可提交")
    submission = db.scalar(select(ExamSubmission).where(ExamSubmission.exam_id == exam_id, ExamSubmission.student_id == current_user.id))
    if not submission:
        submission = ExamSubmission(exam_id=exam_id, student_id=current_user.id, started_at=datetime.now(UTC))
        db.add(submission)
        db.flush()
    submission.status = "submitted"
    submission.answers = payload.answers
    submission.score = payload.score
    submission.submitted_at = datetime.now(UTC)
    grade = db.scalar(select(ExamGrade).where(ExamGrade.exam_id == exam_id, ExamGrade.student_id == current_user.id))
    if not grade:
        grade = ExamGrade(exam_id=exam_id, student_id=current_user.id, score=payload.score)
        db.add(grade)
    else:
        grade.score = payload.score
    db.commit()
    db.refresh(submission)
    return submission


@router.get("/{exam_id}/grades", response_model=PaginatedResponse)
def exam_grades(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    exam = require_exam(exam_id, db)
    if current_user.role == "teacher":
        ensure_course_manager(exam.course, current_user)
    grades = db.scalars(select(ExamGrade).where(ExamGrade.exam_id == exam_id).order_by(ExamGrade.id)).all()
    return PaginatedResponse(items=[ExamGradeRead.model_validate(grade) for grade in grades], page=1, page_size=len(grades) or 20, total=len(grades))

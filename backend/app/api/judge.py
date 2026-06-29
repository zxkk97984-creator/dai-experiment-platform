from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.assignments import require_assignment
from app.api.courses import can_view_course
from app.config import Settings, get_settings
from app.dependencies import get_current_user, get_db, get_redis_client
from app.errors import api_error
from app.models import Assignment, Course, JudgeQuestion, Submission, User
from app.schemas import PaginatedResponse, SubmissionCreate, SubmissionRead

router = APIRouter(prefix="/judge", tags=["judge"])


def require_submission(submission_id: int, db: Session) -> Submission:
    submission = db.get(Submission, submission_id)
    if not submission:
        raise api_error(404, "SUBMISSION_NOT_FOUND", "提交不存在")
    return submission


def can_view_submission(submission: Submission, user: User, db: Session) -> bool:
    if user.role in {"admin", "teacher"}:
        return True
    return submission.student_id == user.id


@router.post("/submissions", response_model=SubmissionRead, status_code=status.HTTP_201_CREATED)
def create_submission(
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "student":
        raise api_error(403, "FORBIDDEN", "只有学生可以提交代码")
    question = db.get(JudgeQuestion, payload.question_id)
    if not question:
        raise api_error(404, "QUESTION_NOT_FOUND", "题目不存在")
    assignment = db.get(Assignment, question.assignment_id)
    if not assignment or assignment.status != "published":
        raise api_error(400, "ASSIGNMENT_NOT_AVAILABLE", "作业不可提交")
    course = db.get(Course, assignment.course_id)
    if not course or not can_view_course(course, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限提交该题目")
    submission = Submission(
        question_id=payload.question_id,
        student_id=current_user.id,
        code=payload.code,
        status="queued",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    redis_client.lpush(settings.judge_queue_name, str(submission.id))
    return submission


@router.get("/submissions", response_model=PaginatedResponse)
def list_submissions(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Submission)
    count_query = select(func.count()).select_from(Submission)
    if current_user.role == "student":
        query = query.where(Submission.student_id == current_user.id)
        count_query = count_query.where(Submission.student_id == current_user.id)
    total = db.scalar(count_query) or 0
    submissions = db.scalars(query.order_by(Submission.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return PaginatedResponse(items=[SubmissionRead.model_validate(item) for item in submissions], page=page, page_size=page_size, total=total)


@router.get("/submissions/{submission_id}", response_model=SubmissionRead)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = require_submission(submission_id, db)
    if not can_view_submission(submission, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限查看该提交")
    return submission


@router.get("/submissions/{submission_id}/result", response_model=SubmissionRead)
def get_submission_result(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = require_submission(submission_id, db)
    if not can_view_submission(submission, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限查看该判题结果")
    return submission


@router.post("/questions/{question_id}/sample-run", response_model=SubmissionRead)
def sample_run(
    question_id: int,
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if question_id != payload.question_id:
        raise api_error(400, "QUESTION_MISMATCH", "题目 ID 不一致")
    question = db.get(JudgeQuestion, question_id)
    if not question:
        raise api_error(404, "QUESTION_NOT_FOUND", "题目不存在")
    submission = Submission(
        question_id=question_id,
        student_id=current_user.id,
        code=payload.code,
        status="queued",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission

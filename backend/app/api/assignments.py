from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.courses import can_view_course, require_course
from app.config import Settings, get_settings
from app.dependencies import get_current_user, get_db, require_roles
from app.errors import api_error
from app.models import Assignment, Course, CourseEnrollment, JudgeQuestion, User
from app.schemas import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    JudgeQuestionCreate,
    JudgeQuestionRead,
    PaginatedResponse,
)

router = APIRouter(prefix="/assignments", tags=["assignments"])


def require_assignment(assignment_id: int, db: Session) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if not assignment:
        raise api_error(404, "ASSIGNMENT_NOT_FOUND", "作业不存在")
    return assignment


def ensure_assignment_manager(assignment: Assignment, user: User, db: Session):
    if user.role == "admin":
        return
    course = db.get(Course, assignment.course_id)
    if user.role == "teacher" and course and course.teacher_id == user.id:
        return
    raise api_error(403, "FORBIDDEN", "没有权限管理该作业")


@router.get("", response_model=PaginatedResponse)
def list_assignments(
    course_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Assignment)
    count_query = select(func.count()).select_from(Assignment)
    if course_id:
        query = query.where(Assignment.course_id == course_id)
        count_query = count_query.where(Assignment.course_id == course_id)
    if current_user.role == "student":
        # 学生只看到 published assignment + published course + enrolled
        query = (
            query.join(Course, Assignment.course_id == Course.id)
            .join(CourseEnrollment, Course.id == CourseEnrollment.course_id)
            .where(Assignment.status == "published")
            .where(Course.status == "published")
            .where(CourseEnrollment.student_id == current_user.id)
            .where(CourseEnrollment.status == "enrolled")
        )
        count_query = (
            count_query.join(Course, Assignment.course_id == Course.id)
            .join(CourseEnrollment, Course.id == CourseEnrollment.course_id)
            .where(Assignment.status == "published")
            .where(Course.status == "published")
            .where(CourseEnrollment.student_id == current_user.id)
            .where(CourseEnrollment.status == "enrolled")
        )
    elif current_user.role == "teacher":
        query = query.join(Course, Assignment.course_id == Course.id).where(Course.teacher_id == current_user.id)
        count_query = count_query.join(Course, Assignment.course_id == Course.id).where(Course.teacher_id == current_user.id)
    elif current_user.role != "admin":
        # developer or any unsupported role: empty
        query = query.where(Assignment.id == -1)
        count_query = count_query.where(Assignment.id == -1)
    total = db.scalar(count_query) or 0
    assignments = db.scalars(query.order_by(Assignment.id).offset((page - 1) * page_size).limit(page_size)).all()
    return PaginatedResponse(items=[AssignmentRead.model_validate(item) for item in assignments], page=page, page_size=page_size, total=total)


@router.post("", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
def create_assignment(
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    course = require_course(payload.course_id, db)
    if current_user.role == "teacher":
        if course.teacher_id != current_user.id:
            raise api_error(403, "FORBIDDEN", "只能在自己的课程中创建作业")
    assignment = Assignment(**payload.model_dump(), created_by_id=current_user.id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/{assignment_id}", response_model=AssignmentRead)
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignment = require_assignment(assignment_id, db)
    course = db.get(Course, assignment.course_id)
    if not course or not can_view_course(course, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限查看该作业")
    if current_user.role == "student" and assignment.status != "published":
        raise api_error(403, "ASSIGNMENT_NOT_AVAILABLE", "作业未发布")
    return assignment


@router.patch("/{assignment_id}", response_model=AssignmentRead)
def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignment = require_assignment(assignment_id, db)
    ensure_assignment_manager(assignment, current_user, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(assignment, key, value)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/{assignment_id}/publish", response_model=AssignmentRead)
def publish_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    assignment = require_assignment(assignment_id, db)
    ensure_assignment_manager(assignment, current_user, db)

    # AI 评分门禁：非 legacy 题目需要锁定 Rubric
    questions = db.scalars(
        select(JudgeQuestion).where(
            JudgeQuestion.assignment_id == assignment_id,
            JudgeQuestion.grading_mode != "legacy",
        )
    ).all()

    if questions:
        if not settings.ai_ready:
            raise api_error(503, "AI_NOT_READY", "发布含 AI 评分的题目需要配置 DAI_AI_API_KEY")
        from app.services.ai_client import DeepSeekClient, AIServiceError
        from app.services.rubric_service import ensure_locked_rubrics_for_publish
        try:
            client = DeepSeekClient(settings)
            ensure_locked_rubrics_for_publish(db, client, questions)
        except AIServiceError as exc:
            raise api_error(503, "AI_RUBRIC_UNAVAILABLE", f"Rubric 生成失败: {exc}")

    assignment.status = "published"
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/{assignment_id}/questions", response_model=PaginatedResponse)
def list_questions(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignment = require_assignment(assignment_id, db)
    course = db.get(Course, assignment.course_id)
    if not course or not can_view_course(course, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限查看题目")
    if current_user.role == "student" and assignment.status != "published":
        raise api_error(403, "ASSIGNMENT_NOT_AVAILABLE", "作业未发布")
    questions = db.scalars(select(JudgeQuestion).where(JudgeQuestion.assignment_id == assignment_id).order_by(JudgeQuestion.id)).all()
    return PaginatedResponse(items=[JudgeQuestionRead.model_validate(question) for question in questions], page=1, page_size=len(questions) or 20, total=len(questions))


@router.post("/{assignment_id}/questions", response_model=JudgeQuestionRead, status_code=status.HTTP_201_CREATED)
def create_question(
    assignment_id: int,
    payload: JudgeQuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignment = require_assignment(assignment_id, db)
    ensure_assignment_manager(assignment, current_user, db)
    data = payload.model_dump(exclude_unset=True)
    question = JudgeQuestion(assignment_id=assignment_id, **data)
    # 新建编程题默认 shadow 模式（仅当用户未显式指定时生效）
    if "grading_mode" not in data:
        question.grading_mode = "shadow"
    db.add(question)
    db.commit()
    db.refresh(question)
    return question

from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.courses import can_view_course, ensure_course_manager, require_course
from app.dependencies import get_current_user, get_db, require_roles
from app.errors import api_error
from app.models import Course, CourseEnrollment, Exam, ExamAnswer, ExamGrade, ExamQuestion, ExamSubmission, User
from app.schemas import ExamCreate, ExamGradeRead, ExamQuestionCreate, ExamQuestionRead, ExamQuestionUpdate, ExamRead, ExamSubmitRequest, ExamSubmissionRead, ExamUpdate, PaginatedResponse
from app.services.exam_service import create_question, delete_question, get_my_grade, get_question, list_questions, require_exam_editable, save_answer, start_exam as svc_start_exam, submit_exam as svc_submit_exam, update_question, validate_publish

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
    return PaginatedResponse(items=[ExamRead.model_validate(exam) for exam in exams], page=page, page_size=page_size, total=total)


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
    if not can_view_course(exam.course, current_user, db):
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
):
    exam = require_exam(exam_id, db)
    ensure_course_manager(exam.course, current_user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(exam, key, value)
    # 发布时强制校验
    if exam.status == "published":
        validate_publish(exam, db)
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
    if not course or not can_view_course(course, current_user, db):
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
    if not course or not can_view_course(course, current_user, db):
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
    # 幂等：重复提交返回当前状态，不报错
    if sub.status in ("submitted", "grading", "graded"):
        return ExamSubmissionRead.model_validate(sub)
    return svc_submit_exam(exam, current_user, db)


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


# ── 考试题目管理 ──

@router.get("/{exam_id}/questions", response_model=PaginatedResponse)
def get_questions(exam_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    exam = require_exam(exam_id, db)
    if current_user.role == "student":
        # 学生必须已选课且考试已发布
        if exam.status != "published":
            raise api_error(403, "EXAM_NOT_AVAILABLE", "考试未发布")
        if not can_view_course(exam.course, current_user, db):
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
    items = [ExamQuestionRead.model_validate(q) for q in questions]
    return PaginatedResponse(items=items, page=1, page_size=len(items), total=len(items))

@router.post("/{exam_id}/questions", response_model=ExamQuestionRead, status_code=status.HTTP_201_CREATED)
def post_question(exam_id: int, payload: ExamQuestionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return create_question(db, exam_id, payload.model_dump(), current_user)

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

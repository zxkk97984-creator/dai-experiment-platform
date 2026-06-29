from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.dependencies import get_current_user, get_db, require_roles
from app.errors import api_error
from app.models import Chapter, Course, CourseEnrollment, Lesson, User
from app.schemas import (
    ChapterCreate,
    ChapterRead,
    CourseCreate,
    CourseRead,
    CourseUpdate,
    EnrollmentRead,
    LessonCreate,
    LessonRead,
    PaginatedResponse,
)

router = APIRouter(tags=["courses"])


def require_course(course_id: int, db: Session) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise api_error(404, "COURSE_NOT_FOUND", "课程不存在")
    return course


def require_chapter(chapter_id: int, db: Session) -> Chapter:
    chapter = db.get(Chapter, chapter_id)
    if not chapter:
        raise api_error(404, "CHAPTER_NOT_FOUND", "章节不存在")
    return chapter


def ensure_course_manager(course: Course, user: User):
    if user.role == "admin":
        return
    if user.role == "teacher" and course.teacher_id == user.id:
        return
    raise api_error(403, "FORBIDDEN", "没有权限管理该课程")


def can_view_course(course: Course, user: User, db: Session) -> bool:
    if user.role in {"admin", "teacher", "developer"}:
        return True
    if course.status == "published":
        return True
    return bool(
        db.scalar(
            select(CourseEnrollment).where(
                CourseEnrollment.course_id == course.id,
                CourseEnrollment.student_id == user.id,
                CourseEnrollment.status == "enrolled",
            )
        )
    )


@router.get("/courses", response_model=PaginatedResponse)
def list_courses(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Course)
    count_query = select(func.count()).select_from(Course)
    if current_user.role == "student":
        query = query.where(Course.status == "published")
        count_query = count_query.where(Course.status == "published")
    elif current_user.role == "teacher":
        query = query.where(Course.teacher_id == current_user.id)
        count_query = count_query.where(Course.teacher_id == current_user.id)
    total = db.scalar(count_query) or 0
    courses = db.scalars(query.order_by(Course.id).offset((page - 1) * page_size).limit(page_size)).all()
    return PaginatedResponse(items=[CourseRead.model_validate(course) for course in courses], page=page, page_size=page_size, total=total)


@router.post("/courses", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    course = Course(
        title=payload.title,
        description=payload.description,
        status=payload.status,
        teacher_id=current_user.id if current_user.role == "teacher" else None,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/courses/{course_id}", response_model=CourseRead)
def get_course(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course = require_course(course_id, db)
    if not can_view_course(course, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限查看该课程")
    return course


@router.patch("/courses/{course_id}", response_model=CourseRead)
def update_course(
    course_id: int,
    payload: CourseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = require_course(course_id, db)
    ensure_course_manager(course, current_user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, key, value)
    db.commit()
    db.refresh(course)
    return course


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_course(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course = require_course(course_id, db)
    ensure_course_manager(course, current_user)
    course.status = "archived"
    db.commit()
    return None


@router.post("/courses/{course_id}/enroll", response_model=EnrollmentRead, status_code=status.HTTP_201_CREATED)
def enroll_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    course = require_course(course_id, db)
    if course.status != "published":
        raise api_error(400, "COURSE_NOT_PUBLISHED", "课程尚未发布")
    enrollment = db.scalar(
        select(CourseEnrollment).where(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.student_id == current_user.id,
        )
    )
    if enrollment:
        enrollment.status = "enrolled"
    else:
        enrollment = CourseEnrollment(course_id=course_id, student_id=current_user.id, status="enrolled")
        db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


@router.delete("/courses/{course_id}/enroll", status_code=status.HTTP_204_NO_CONTENT)
def drop_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    enrollment = db.scalar(
        select(CourseEnrollment).where(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.student_id == current_user.id,
        )
    )
    if enrollment:
        enrollment.status = "dropped"
        db.commit()
    return None


@router.get("/courses/{course_id}/chapters", response_model=PaginatedResponse)
def list_chapters(
    course_id: int,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = require_course(course_id, db)
    if not can_view_course(course, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限查看该课程章节")
    query = (
        select(Chapter)
        .where(Chapter.course_id == course_id)
        .options(selectinload(Chapter.lessons))
        .order_by(Chapter.order_index, Chapter.id)
    )
    total = db.scalar(select(func.count()).select_from(Chapter).where(Chapter.course_id == course_id)) or 0
    chapters = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return PaginatedResponse(items=[ChapterRead.model_validate(chapter) for chapter in chapters], page=page, page_size=page_size, total=total)


@router.post("/courses/{course_id}/chapters", response_model=ChapterRead, status_code=status.HTTP_201_CREATED)
def create_chapter(
    course_id: int,
    payload: ChapterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = require_course(course_id, db)
    ensure_course_manager(course, current_user)
    chapter = Chapter(course_id=course_id, title=payload.title, order_index=payload.order_index)
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


@router.post("/chapters/{chapter_id}/lessons", response_model=LessonRead, status_code=status.HTTP_201_CREATED)
def create_lesson(
    chapter_id: int,
    payload: LessonCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chapter = require_chapter(chapter_id, db)
    ensure_course_manager(chapter.course, current_user)
    lesson = Lesson(chapter_id=chapter_id, **payload.model_dump())
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson


@router.patch("/lessons/{lesson_id}", response_model=LessonRead)
def update_lesson(
    lesson_id: int,
    payload: LessonCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise api_error(404, "LESSON_NOT_FOUND", "课时不存在")
    ensure_course_manager(lesson.chapter.course, current_user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(lesson, key, value)
    db.commit()
    db.refresh(lesson)
    return lesson

from fastapi import APIRouter, Depends, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.dependencies import get_current_user, get_db, require_roles
from app.errors import api_error
from app.services.lesson_video_service import remove_storage_key
from app.models import Chapter, Course, CourseEnrollment, CourseWhitelistStudent, Lesson, User
from app.schemas import (
    ChapterCreate,
    ChapterRead,
    ChapterUpdate,
    CourseCreate,
    CourseRead,
    CourseUpdate,
    CourseWhitelistCreate,
    CourseWhitelistEntryRead,
    CourseWhitelistListRead,
    EnrollmentRead,
    LessonCreate,
    LessonRead,
    LessonUpdate,
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


def is_student_enrolled(course_id: int, student_id: int, db: Session) -> bool:
    """学生是否已选课且 enrollment 状态为 enrolled"""
    return bool(
        db.scalar(
            select(CourseEnrollment).where(
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.student_id == student_id,
                CourseEnrollment.status == "enrolled",
            )
        )
    )


def has_enrollment_record(course_id: int, student_id: int, db: Session) -> bool:
    """是否存在任意状态的 enrollment 记录（含 dropped）"""
    return bool(
        db.scalar(
            select(CourseEnrollment.id).where(
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.student_id == student_id,
            )
        )
    )


def is_student_whitelisted(course_id: int, student_id: int, db: Session) -> bool:
    """学生是否在课程白名单中"""
    return bool(
        db.scalar(
            select(CourseWhitelistStudent.id).where(
                CourseWhitelistStudent.course_id == course_id,
                CourseWhitelistStudent.student_id == student_id,
            )
        )
    )


def can_view_course(course: Course, user: User, db: Session) -> bool:
    """课程可见性：能否发现课程、读取课程元数据。

    - admin：任意课程
    - teacher：仅自己的课程
    - student：published + public / 白名单成员 / 存量已选（private）
    - 其他角色（developer 等）：fail closed
    """
    if user.role == "admin":
        return True
    if user.role == "teacher":
        return course.teacher_id == user.id
    if user.role != "student":
        return False
    if course.status != "published":
        return False
    if course.visibility == "public":
        return True
    if course.visibility == "whitelist":
        return is_student_whitelisted(course.id, user.id, db)
    if course.visibility == "private":
        # 保留存量已选学生的访问
        return is_student_enrolled(course.id, user.id, db)
    # 非法/未知数据库值 fail closed
    return False


def can_access_course_content(course: Course, user: User, db: Session) -> bool:
    """内容权限：能否读取章节/课时或参加作业、考试、提交等学习活动。

    学生必须同时满足可见性要求与有效选课；白名单只决定能否发现并选课，不能替代选课。
    """
    if user.role in ("admin", "teacher"):
        return can_view_course(course, user, db)
    if user.role == "student":
        return (
            can_view_course(course, user, db)
            and is_student_enrolled(course.id, user.id, db)
        )
    return False


def serialize_course(course: Course, is_enrolled: bool = False, can_enroll: bool = False) -> CourseRead:
    """构造带学生选课状态的 CourseRead 响应"""
    data = CourseRead.model_validate(course).model_dump()
    data["is_enrolled"] = is_enrolled
    data["can_enroll"] = can_enroll
    return CourseRead.model_validate(data)


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
        # 可见范围：public 全部；whitelist 需白名单关联；private 需存量有效选课
        whitelist_exists = (
            select(CourseWhitelistStudent.id)
            .where(
                CourseWhitelistStudent.course_id == Course.id,
                CourseWhitelistStudent.student_id == current_user.id,
            )
            .exists()
        )
        enrolled_exists = (
            select(CourseEnrollment.id)
            .where(
                CourseEnrollment.course_id == Course.id,
                CourseEnrollment.student_id == current_user.id,
                CourseEnrollment.status == "enrolled",
            )
            .exists()
        )
        student_predicate = and_(
            Course.status == "published",
            or_(
                Course.visibility == "public",
                and_(Course.visibility == "whitelist", whitelist_exists),
                and_(Course.visibility == "private", enrolled_exists),
            ),
        )
        query = query.where(student_predicate)
        count_query = count_query.where(student_predicate)
    elif current_user.role == "teacher":
        query = query.where(Course.teacher_id == current_user.id)
        count_query = count_query.where(Course.teacher_id == current_user.id)
    elif current_user.role == "developer":
        query = query.where(Course.id == -1)  # empty
        count_query = count_query.where(Course.id == -1)
    total = db.scalar(count_query) or 0
    courses = db.scalars(query.order_by(Course.id).offset((page - 1) * page_size).limit(page_size)).all()
    items = [
        serialize_course(course, is_enrolled, can_enroll)
        for course, is_enrolled, can_enroll in _course_student_flags(courses, current_user, db)
    ]
    return PaginatedResponse(items=items, page=page, page_size=page_size, total=total)


def _course_student_flags(courses, current_user: User, db: Session):
    """批量计算本页课程的 is_enrolled / can_enroll（学生视角）"""
    if current_user.role != "student" or not courses:
        return [(course, False, False) for course in courses]
    enrolled_ids = set(
        db.scalars(
            select(CourseEnrollment.course_id).where(
                CourseEnrollment.student_id == current_user.id,
                CourseEnrollment.status == "enrolled",
                CourseEnrollment.course_id.in_([c.id for c in courses]),
            )
        ).all()
    )
    flags = []
    for course in courses:
        is_enrolled = course.id in enrolled_ids
        if is_enrolled:
            can_enroll = False
        elif course.visibility == "public":
            can_enroll = True
        elif course.visibility == "whitelist":
            # 能出现在学生结果中的 whitelist 课程即白名单成员
            can_enroll = True
        else:
            can_enroll = False
        flags.append((course, is_enrolled, can_enroll))
    return flags


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
        cover=payload.cover,
        start_time=payload.start_time,
        visibility=payload.visibility,
        default_score=payload.default_score,
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
    is_enrolled = False
    can_enroll = False
    if current_user.role == "student":
        is_enrolled = is_student_enrolled(course.id, current_user.id, db)
        can_enroll = not is_enrolled and course.visibility in ("public", "whitelist")
    return serialize_course(course, is_enrolled, can_enroll)


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
    if course.visibility == "public":
        pass  # 所有学生可选
    elif course.visibility == "whitelist":
        if not is_student_whitelisted(course.id, current_user.id, db):
            raise api_error(403, "COURSE_NOT_VISIBLE", "没有权限选修该课程")
    elif course.visibility == "private":
        # 禁止从未选课学生首次自助选课；已有 enrollment 记录（含 dropped）可恢复
        if enrollment is None:
            raise api_error(403, "COURSE_NOT_VISIBLE", "没有权限选修该课程")
    else:
        raise api_error(403, "COURSE_NOT_VISIBLE", "没有权限选修该课程")
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
    if not can_access_course_content(course, current_user, db):
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
    payload: LessonUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    """更新课时：支持标题/内容/发布状态，传 chapter_id 可移动到其他章节。

    视频语义：
    - 非空 video_url：切换为 external，清空上传元数据，提交成功后删除旧本地文件；
    - video_url=None 且当前来源为 upload：不得隐式删除本地文件（必须走专用 DELETE 接口）；
    - content_type 从 video 改为其他类型：清空全部视频字段并清理本地文件。
    """
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise api_error(404, "LESSON_NOT_FOUND", "课时不存在")
    ensure_course_manager(lesson.chapter.course, current_user)
    data = payload.model_dump(exclude_unset=True)
    if data.get("chapter_id") is not None and data["chapter_id"] != lesson.chapter_id:
        target = db.get(Chapter, data["chapter_id"])
        if not target or target.course_id != lesson.chapter.course_id:
            raise api_error(400, "INVALID_CHAPTER", "目标章节不存在或不属于同一课程")

    old_key = lesson.video_storage_key
    clear_files = False  # 提交成功后需要删除旧本地文件
    if "video_url" in data and data["video_url"]:
        # 写入非空外链：切换为 external 并清空上传元数据
        if lesson.video_source == "upload":
            lesson.video_source = "external"
            lesson.video_storage_key = None
            lesson.video_filename = None
            lesson.video_content_type = None
            lesson.video_size = None
            clear_files = True
    if (
        data.get("content_type")
        and data["content_type"] != lesson.content_type
        and lesson.content_type == "video"
    ):
        # 视频课时改为其他类型：清空全部视频字段并清理本地文件
        lesson.video_source = "external"
        lesson.video_storage_key = None
        lesson.video_filename = None
        lesson.video_content_type = None
        lesson.video_size = None
        lesson.video_url = None
        clear_files = True

    for key, value in data.items():
        setattr(lesson, key, value)
    db.commit()
    db.refresh(lesson)
    if clear_files and old_key:
        remove_storage_key(settings, old_key)
    return lesson


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise api_error(404, "LESSON_NOT_FOUND", "课时不存在")
    ensure_course_manager(lesson.chapter.course, current_user)
    # 删除前保存 storage key，数据库提交成功后清理本地文件
    old_key = lesson.video_storage_key
    db.delete(lesson)
    db.commit()
    if old_key:
        remove_storage_key(settings, old_key)


@router.patch("/chapters/{chapter_id}", response_model=ChapterRead)
def update_chapter(
    chapter_id: int,
    payload: ChapterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑章节：标题 / 排序位置（移动章节）"""
    chapter = db.get(Chapter, chapter_id)
    if not chapter:
        raise api_error(404, "CHAPTER_NOT_FOUND", "章节不存在")
    ensure_course_manager(chapter.course, current_user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(chapter, key, value)
    db.commit()
    db.refresh(chapter)
    return chapter


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(
    chapter_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    """删除章节：级联删除章节内全部课时，并清理章节内所有本地视频文件"""
    chapter = db.get(Chapter, chapter_id)
    if not chapter:
        raise api_error(404, "CHAPTER_NOT_FOUND", "章节不存在")
    ensure_course_manager(chapter.course, current_user)
    # 删除前收集章节内全部本地视频 key，级联删除成功后逐个清理文件
    old_keys = [l.video_storage_key for l in chapter.lessons if l.video_storage_key]
    db.delete(chapter)
    db.commit()
    for key in old_keys:
        remove_storage_key(settings, key)


# ── 课程白名单 ────────────────────────────────────────────────


@router.get("/courses/{course_id}/whitelist", response_model=CourseWhitelistListRead)
def list_whitelist(
    course_id: int,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = require_course(course_id, db)
    ensure_course_manager(course, current_user)
    filters = [CourseWhitelistStudent.course_id == course_id]
    if q:
        like = f"%{q}%"
        filters.append(or_(User.username.ilike(like), User.real_name.ilike(like)))
    query = (
        select(CourseWhitelistStudent)
        .join(User, CourseWhitelistStudent.student_id == User.id)
        .where(*filters)
        .options(selectinload(CourseWhitelistStudent.student))
    )
    count_query = (
        select(func.count())
        .select_from(CourseWhitelistStudent)
        .join(User, CourseWhitelistStudent.student_id == User.id)
        .where(*filters)
    )
    total = db.scalar(count_query) or 0
    entries = db.scalars(
        query.order_by(CourseWhitelistStudent.id)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return CourseWhitelistListRead(
        items=[CourseWhitelistEntryRead.model_validate(entry) for entry in entries],
        page=page, page_size=page_size, total=total,
    )


@router.post("/courses/{course_id}/whitelist", response_model=CourseWhitelistEntryRead, status_code=status.HTTP_201_CREATED)
def add_whitelist_student(
    course_id: int,
    payload: CourseWhitelistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = require_course(course_id, db)
    ensure_course_manager(course, current_user)
    student = db.get(User, payload.student_id)
    if not student:
        raise api_error(404, "USER_NOT_FOUND", "用户不存在")
    if student.role != "student":
        raise api_error(400, "INVALID_STUDENT_ROLE", "只有学生可以加入白名单")
    if student.status != "active":
        raise api_error(400, "STUDENT_NOT_ACTIVE", "该学生状态不可用")
    if is_student_whitelisted(course_id, payload.student_id, db):
        raise api_error(409, "WHITELIST_ENTRY_EXISTS", "该学生已在白名单中")
    entry = CourseWhitelistStudent(course_id=course_id, student_id=payload.student_id)
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        # 并发重复插入：唯一约束兜底，回滚后返回同一 409 而非 500
        db.rollback()
        raise api_error(409, "WHITELIST_ENTRY_EXISTS", "该学生已在白名单中")
    db.refresh(entry)
    return entry


@router.delete("/courses/{course_id}/whitelist/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_whitelist_student(
    course_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = require_course(course_id, db)
    ensure_course_manager(course, current_user)
    entry = db.scalar(
        select(CourseWhitelistStudent).where(
            CourseWhitelistStudent.course_id == course_id,
            CourseWhitelistStudent.student_id == student_id,
        )
    )
    if not entry:
        raise api_error(404, "WHITELIST_ENTRY_NOT_FOUND", "该学生不在白名单中")
    # 不删除也不修改 CourseEnrollment；若课程为 whitelist，学生立即失去可见性与内容权限
    db.delete(entry)
    db.commit()
    return None

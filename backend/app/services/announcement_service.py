"""公告可见性服务——供公告 API 与角色首页仪表盘复用，避免 api↔service 循环导入"""

from datetime import datetime

from sqlalchemy import case, false as sa_false, func, or_, select
from sqlalchemy.orm import Session

from app.models import Announcement, AnnouncementRead, Course, CourseEnrollment, User
from app.schemas.announcements import AnnouncementRead as AnnouncementReadSchema


def visible_conditions(user: User):
    """当前用户可见的公告范围条件（不含归档/过期过滤）

    可见性矩阵（显式角色分支，异常 enrollment 不会扩大教师可见范围）：
    - admin：全部公告
    - teacher：全局 + 自己任课的课程
    - student：全局 + 已选课的课程
    - 其他角色（developer 等）：不匹配任何公告
    """
    global_visible = Announcement.scope == "global"
    if user.role == "admin":
        return or_(global_visible, Announcement.scope == "course")
    if user.role == "teacher":
        owned_course_ids = select(Course.id).where(Course.teacher_id == user.id)
        return or_(global_visible, Announcement.course_id.in_(owned_course_ids))
    if user.role == "student":
        enrolled_course_ids = select(CourseEnrollment.course_id).where(
            CourseEnrollment.student_id == user.id,
            CourseEnrollment.status == "enrolled",
        )
        return or_(global_visible, Announcement.course_id.in_(enrolled_course_ids))
    return sa_false()


def list_visible_announcements(
    db: Session, user: User, now: datetime, limit: int = 8
) -> list[AnnouncementReadSchema]:
    """当前用户可见的公告：归档/过期已过滤，按优先级 + 发布时间倒序"""
    priority_order = case(
        (Announcement.priority == "urgent", 0),
        (Announcement.priority == "important", 1),
        else_=2,
    )
    rows = db.execute(
        select(Announcement, Course.title, User.real_name)
        .outerjoin(Course, Course.id == Announcement.course_id)
        .join(User, User.id == Announcement.author_id)
        .where(
            Announcement.archived_at.is_(None),
            or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
            visible_conditions(user),
        )
        .order_by(priority_order, Announcement.published_at.desc())
        .limit(limit)
    ).all()
    if not rows:
        return []
    read_ids = set(
        db.scalars(
            select(AnnouncementRead.announcement_id).where(
                AnnouncementRead.user_id == user.id,
                AnnouncementRead.announcement_id.in_([row[0].id for row in rows]),
            )
        ).all()
    )
    return [
        AnnouncementReadSchema(
            id=notice.id,
            title=notice.title,
            content=notice.content,
            priority=notice.priority,
            scope=notice.scope,
            course_id=notice.course_id,
            course_title=course_title,
            author_name=author_name,
            published_at=notice.published_at,
            expires_at=notice.expires_at,
            is_read=notice.id in read_ids,
        )
        for notice, course_title, author_name in rows
    ]


def unread_announcement_count(db: Session, user: User, now: datetime) -> int:
    """当前用户可见但未标记已读的公告数（不受展示上限影响）"""
    read_ids = select(AnnouncementRead.announcement_id).where(
        AnnouncementRead.user_id == user.id
    )
    return (
        db.scalar(
            select(func.count(Announcement.id)).where(
                Announcement.archived_at.is_(None),
                or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
                visible_conditions(user),
                ~Announcement.id.in_(read_ids),
            )
        )
        or 0
    )

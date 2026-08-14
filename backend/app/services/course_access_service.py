"""课程可见性查询策略。

需要批量筛选课程的入口必须复用这里的 SQL 表达式，避免课程列表、首页聚合等
接口各自复制规则后发生语义漂移。
"""

from sqlalchemy import and_, or_, select

from app.models import (
    Course,
    CourseEnrollment,
    CourseTeachingClass,
    CourseWhitelistStudent,
    TeachingClassStudent,
)


def student_visible_course_predicate(student_id: int):
    """返回学生可发现的已发布课程 SQL 条件。"""
    whitelist_exists = (
        select(CourseWhitelistStudent.id)
        .where(
            CourseWhitelistStudent.course_id == Course.id,
            CourseWhitelistStudent.student_id == student_id,
        )
        .correlate(Course)
        .exists()
    )
    enrolled_exists = (
        select(CourseEnrollment.id)
        .where(
            CourseEnrollment.course_id == Course.id,
            CourseEnrollment.student_id == student_id,
            CourseEnrollment.status == "enrolled",
        )
        .correlate(Course)
        .exists()
    )
    manual_enrollment_exists = (
        select(CourseEnrollment.id)
        .where(
            CourseEnrollment.course_id == Course.id,
            CourseEnrollment.student_id == student_id,
            CourseEnrollment.status == "enrolled",
            CourseEnrollment.origin == "manual",
        )
        .correlate(Course)
        .exists()
    )
    class_member_exists = (
        select(TeachingClassStudent.id)
        .join(
            CourseTeachingClass,
            CourseTeachingClass.teaching_class_id == TeachingClassStudent.teaching_class_id,
        )
        .where(
            CourseTeachingClass.course_id == Course.id,
            TeachingClassStudent.student_id == student_id,
            TeachingClassStudent.status == "active",
        )
        .correlate(Course)
        .exists()
    )
    return and_(
        Course.status == "published",
        or_(
            Course.visibility == "public",
            and_(Course.visibility == "class", or_(class_member_exists, manual_enrollment_exists)),
            and_(Course.visibility == "whitelist", whitelist_exists),
            and_(Course.visibility == "private", enrolled_exists),
        ),
    )

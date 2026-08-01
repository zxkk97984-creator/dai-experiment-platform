"""角色首页聚合响应模型——路由一律为服务端生成的相对路径"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.announcements import AnnouncementRead


# ── 学生首页 ───────────────────────────────────────────────────


class StudentSummary(BaseModel):
    course_count: int = 0
    pending_assignment_count: int = 0
    upcoming_exam_count: int = 0
    unread_announcement_count: int = 0


class PriorityItem(BaseModel):
    kind: str
    id: int
    title: str
    course_title: str | None = None
    time_at: datetime | None = None
    urgency: str = "normal"
    route: str


class ContinueLearning(BaseModel):
    kind: str
    title: str
    subtitle: str | None = None
    updated_at: datetime | None = None
    route: str


class CourseSnapshot(BaseModel):
    id: int
    title: str
    pending_assignment_count: int = 0
    upcoming_exam_count: int = 0
    last_activity_at: datetime | None = None
    route: str


class RecentFeedback(BaseModel):
    kind: str
    id: int
    title: str
    course_title: str | None = None
    score: float | None = None
    feedback: str | None = None
    graded_at: datetime | None = None
    route: str


class StudentDashboardRead(BaseModel):
    summary: StudentSummary = Field(default_factory=StudentSummary)
    priority_items: list[PriorityItem] = Field(default_factory=list)
    continue_learning: ContinueLearning | None = None
    courses: list[CourseSnapshot] = Field(default_factory=list)
    recent_feedback: list[RecentFeedback] = Field(default_factory=list)
    announcements: list[AnnouncementRead] = Field(default_factory=list)


# ── 教师首页 ───────────────────────────────────────────────────


class TeacherSummary(BaseModel):
    course_count: int = 0
    student_count: int = 0
    pending_review_count: int = 0
    upcoming_deadline_count: int = 0


class WorkItem(BaseModel):
    kind: str
    id: int
    title: str
    course_id: int | None = None
    course_title: str | None = None
    detail: str | None = None
    time_at: datetime | None = None
    urgency: str = "normal"
    route: str


class CourseHealth(BaseModel):
    course_id: int
    title: str
    student_count: int = 0
    pending_review_count: int = 0
    upcoming_deadline_count: int = 0
    at_risk_submitted_count: int | None = None
    at_risk_expected_count: int | None = None
    route: str


class TeacherActivity(BaseModel):
    kind: str
    id: int
    title: str
    course_title: str | None = None
    actor_name: str | None = None
    happened_at: datetime | None = None
    route: str


class ManagedCourse(BaseModel):
    id: int
    title: str


class TeacherDashboardRead(BaseModel):
    summary: TeacherSummary = Field(default_factory=TeacherSummary)
    work_items: list[WorkItem] = Field(default_factory=list)
    course_health: list[CourseHealth] = Field(default_factory=list)
    recent_activity: list[TeacherActivity] = Field(default_factory=list)
    managed_courses: list[ManagedCourse] = Field(default_factory=list)
    announcements: list[AnnouncementRead] = Field(default_factory=list)

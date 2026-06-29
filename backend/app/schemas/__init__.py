from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PaginatedResponse(BaseModel):
    items: list[Any]
    page: int = 1
    page_size: int = 20
    total: int = 0


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: str
    role: str
    status: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class UserCreate(BaseModel):
    username: str
    password: str
    real_name: str
    role: str
    status: str = "active"


class UserUpdate(BaseModel):
    real_name: str | None = None
    role: str | None = None
    status: str | None = None


class PasswordUpdate(BaseModel):
    password: str


class StatusUpdate(BaseModel):
    status: str


class CourseCreate(BaseModel):
    title: str
    description: str | None = None
    status: str = "draft"


class CourseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    status: str
    teacher_id: int | None = None


class ChapterCreate(BaseModel):
    title: str
    order_index: int = 0


class LessonCreate(BaseModel):
    title: str
    content_type: str = "markdown"
    content: str | None = None
    notebook_path: str | None = None
    video_url: str | None = None
    order_index: int = 0


class LessonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    title: str
    content_type: str
    content: str | None = None
    notebook_path: str | None = None
    video_url: str | None = None
    order_index: int


class ChapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    order_index: int
    lessons: list[LessonRead] = Field(default_factory=list)


class EnrollmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    student_id: int
    status: str


class AssignmentCreate(BaseModel):
    course_id: int
    title: str
    description: str | None = None
    status: str = "draft"
    due_at: datetime | None = None


class AssignmentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    due_at: datetime | None = None


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    description: str | None = None
    status: str
    due_at: datetime | None = None


class JudgeQuestionCreate(BaseModel):
    title: str
    description: str | None = None
    function_name: str
    signature: str | None = None
    starter_code: str | None = None
    public_cases: list[Any] = Field(default_factory=list)
    hidden_tests: str
    time_limit_ms: int = 10000
    memory_limit_mb: int = 256


class JudgeQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    title: str
    description: str | None = None
    function_name: str
    signature: str | None = None
    starter_code: str | None = None
    public_cases: list[Any] = Field(default_factory=list)
    time_limit_ms: int
    memory_limit_mb: int


class SubmissionCreate(BaseModel):
    question_id: int
    code: str


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_id: int
    student_id: int
    code: str
    status: str
    stdout: str | None = None
    stderr: str | None = None
    score: float | None = None
    result_details: dict | None = None
    execution_time_ms: int | None = None


class ExamCreate(BaseModel):
    course_id: int
    title: str
    status: str = "draft"
    duration_minutes: int = 60
    start_at: datetime | None = None
    end_at: datetime | None = None


class ExamUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    duration_minutes: int | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


class ExamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    status: str
    duration_minutes: int
    start_at: datetime | None = None
    end_at: datetime | None = None


class ExamSubmitRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    score: float = 0


class ExamSubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    student_id: int
    status: str
    answers: dict | None = None
    score: float | None = None


class ExamGradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    student_id: int
    score: float


class ExperimentModuleCreate(BaseModel):
    name: str
    description: str | None = None
    entry_url: str | None = None
    status: str = "draft"


class ExperimentModuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    entry_url: str | None = None
    status: str


class ExperimentRecordCreate(BaseModel):
    module_id: int
    status: str = "started"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperimentRecordRead(BaseModel):
    id: int
    module_id: int
    student_id: int
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class JupyterEntryResponse(BaseModel):
    iframe_url: str


class NotebookTemplateRead(BaseModel):
    id: str
    name: str
    path: str


class NotebookCopyResponse(BaseModel):
    template_id: str
    target_path: str
